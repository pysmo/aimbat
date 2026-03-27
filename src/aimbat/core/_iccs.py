"""Processing of data for AIMBAT."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from pandas import Timestamp
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from pysmo.tools.iccs import (
    ICCS,
    IccsResult,
    McccResult,
    MiniIccsSeismogram,
)

from aimbat import settings
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatSnapshot,
)
from aimbat.models._parameters import (
    AimbatEventParametersBase,
    AimbatSeismogramParametersBase,
)
from aimbat.utils import rel

__all__ = [
    "BoundICCS",
    "build_iccs_from_snapshot",
    "clear_iccs_cache",
    "clear_mccc_quality",
    "create_iccs_instance",
    "run_iccs",
    "run_mccc",
    "sync_iccs_parameters",
    "validate_iccs_construction",
]


@dataclass
class BoundICCS:
    """An ICCS instance explicitly bound to a specific event.

    Use `is_stale` to detect whether the event's parameters have been modified
    (e.g. by a CLI command) since this instance was created.
    """

    iccs: ICCS
    event_id: UUID
    created_at: Timestamp

    def is_stale(self, event: AimbatEvent) -> bool:
        """Return True if the event has been modified since this ICCS was created.

        Args:
            event: The event to check against.
        """
        if event.id != self.event_id:
            return True
        if event.last_modified is None:
            return False
        return event.last_modified > self.created_at


# Process-level ICCS cache. In normal CLI use this is always cold (one command
# per process). In the shell a warm entry is reused across commands, avoiding
# redundant data loading and ICCS computation.
_iccs_cache: dict[UUID, BoundICCS] = {}


def clear_iccs_cache() -> None:
    """Clear the process-level ICCS cache."""
    _iccs_cache.clear()


def _build_iccs(
    event: AimbatEvent, parameters: AimbatEventParametersBase | None = None
) -> ICCS:
    """Build an ICCS instance from an event's parameters and seismograms.

    Args:
        event: AimbatEvent.
        parameters: Optional AimbatEventParametersBase to use instead of the live
            event parameters (useful for validation).

    Returns:
        A freshly constructed ICCS instance.

    """
    p = parameters or event.parameters
    seismograms = [
        MiniIccsSeismogram(
            begin_time=seis.begin_time,
            delta=seis.delta,
            data=seis.data,
            t0=seis.t0,
            t1=seis.t1,
            flip=seis.flip,
            select=seis.select,
            extra={"id": seis.id},
        )
        for seis in event.seismograms
    ]
    return ICCS(
        seismograms=seismograms,
        window_pre=p.window_pre,
        window_post=p.window_post,
        ramp_width=p.ramp_width,
        bandpass_apply=p.bandpass_apply,
        bandpass_fmin=p.bandpass_fmin,
        bandpass_fmax=p.bandpass_fmax,
        min_cc=p.min_cc,
        context_width=settings.context_width,
    )


def create_iccs_instance(session: Session, event: AimbatEvent) -> BoundICCS:
    """Return a BoundICCS instance for the given event.

    Returns the cached instance when it is still fresh (i.e. `event.last_modified`
    has not advanced since the instance was created). Otherwise builds a new one
    and updates the cache. ICCS CC values are written to the live quality table in
    a separate session so the caller's session is not affected.

    `MiniIccsSeismogram` instances are constructed directly from each
    `AimbatSeismogram`, passing `data` by reference to the read-only io cache.
    No waveform data is copied.

    Args:
        session: Database session.
        event: AimbatEvent.

    Returns:
        BoundICCS instance tied to the given event.

    """
    cached = _iccs_cache.get(event.id)
    if cached is not None and not cached.is_stale(event):
        logger.debug(f"Returning cached BoundICCS for event {event.id}.")
        return cached

    event = session.exec(
        select(AimbatEvent)
        .where(AimbatEvent.id == event.id)
        .options(
            selectinload(rel(AimbatEvent.parameters)),
            selectinload(rel(AimbatEvent.seismograms)).selectinload(
                rel(AimbatSeismogram.parameters)
            ),
        )
    ).one()

    logger.debug(f"Creating ICCS instance for event {event.id}.")
    bound = BoundICCS(
        iccs=_build_iccs(event),
        event_id=event.id,
        created_at=Timestamp.now("UTC"),
    )
    _iccs_cache[event.id] = bound
    _write_iccs_stats(event.id, bound.iccs)
    return bound


def _write_iccs_stats(event_id: UUID, iccs: ICCS) -> None:
    """Upsert per-seismogram ICCS CC values into the live quality table.

    Iterates over the seismograms in the ICCS instance and writes (or
    overwrites) the Pearson cross-correlation coefficient for each one, preserving
    any existing MCCC fields.

    Uses its own short-lived session so that the caller's session is not
    committed or expired as a side-effect.

    Args:
        event_id: UUID of the event whose seismograms are being updated.
        iccs: ICCS instance whose `ccs` values are written.
    """
    from aimbat.db import engine as _engine
    from aimbat.models import AimbatSeismogramQuality

    logger.debug(f"Writing ICCS stats for event {event_id}.")
    with Session(_engine) as write_session:
        for iccs_seis, cc in zip(iccs.seismograms, iccs.ccs):
            seis_id = iccs_seis.extra["id"]
            existing = write_session.exec(
                select(AimbatSeismogramQuality).where(
                    col(AimbatSeismogramQuality.seismogram_id) == seis_id
                )
            ).first()
            cc_val = max(-1.0, min(1.0, float(cc)))
            if existing is None:
                row = AimbatSeismogramQuality(
                    id=uuid4(), seismogram_id=seis_id, iccs_cc=cc_val
                )
                write_session.add(row)
            else:
                existing.iccs_cc = cc_val
                write_session.add(existing)
        write_session.commit()


def _write_mccc_quality(
    event_id: UUID, iccs: ICCS, result: McccResult, all_seismograms: bool
) -> None:
    """Write MCCC quality results to the live quality tables.

    Upserts the event-level RMSE, clears MCCC fields for all seismograms in
    the ICCS instance, then writes the per-seismogram metrics for the seismograms
    that were actually used in the inversion. The `iccs_cc` field is preserved
    when an existing quality row is found; seismograms with no prior quality row
    will have `iccs_cc = NULL` until ICCS stats are written separately.

    Uses its own short-lived session.

    Args:
        event_id: UUID of the event that was processed.
        iccs: ICCS instance used for the MCCC run.
        result: McccResult returned by `ICCS.run_mccc`.
        all_seismograms: Whether the run included all seismograms (`True`) or
            only the selected ones (`False`).
    """
    from aimbat.db import engine as _engine
    from aimbat.models import AimbatEventQuality, AimbatSeismogramQuality

    used_seis = (
        iccs.seismograms
        if all_seismograms
        else [s for s in iccs.seismograms if s.select]
    )

    logger.debug(f"Writing MCCC quality for event {event_id}.")
    with Session(_engine) as write_session:
        # Event quality
        existing_eq = write_session.exec(
            select(AimbatEventQuality).where(
                col(AimbatEventQuality.event_id) == event_id
            )
        ).first()
        if existing_eq is None:
            eq = AimbatEventQuality(
                id=uuid4(), event_id=event_id, mccc_rmse=result.rmse
            )
            write_session.add(eq)
        else:
            existing_eq.mccc_rmse = result.rmse
            write_session.add(existing_eq)

        # Clear MCCC fields for all seismograms first
        for iccs_seis in iccs.seismograms:
            seis_id = iccs_seis.extra["id"]
            sq = write_session.exec(
                select(AimbatSeismogramQuality).where(
                    col(AimbatSeismogramQuality.seismogram_id) == seis_id
                )
            ).first()
            if sq is not None:
                sq.mccc_error = None
                sq.mccc_cc_mean = None
                sq.mccc_cc_std = None
                write_session.add(sq)

        # Write MCCC metrics for used seismograms
        for iccs_seis, error, cc_mean, cc_std in zip(
            used_seis, result.errors, result.cc_means, result.cc_stds
        ):
            seis_id = iccs_seis.extra["id"]
            sq = write_session.exec(
                select(AimbatSeismogramQuality).where(
                    col(AimbatSeismogramQuality.seismogram_id) == seis_id
                )
            ).first()
            if sq is None:
                sq = AimbatSeismogramQuality(
                    id=uuid4(),
                    seismogram_id=seis_id,
                    mccc_error=error,
                    mccc_cc_mean=float(cc_mean),
                    mccc_cc_std=float(cc_std),
                )
                write_session.add(sq)
            else:
                sq.mccc_error = error
                sq.mccc_cc_mean = float(cc_mean)
                sq.mccc_cc_std = float(cc_std)
                write_session.add(sq)

        write_session.commit()


def clear_mccc_quality(session: Session, event: AimbatEvent) -> None:
    """Clear MCCC quality metrics from the live quality tables for an event.

    Sets all MCCC fields (`mccc_rmse`, `mccc_error`, `mccc_cc_mean`,
    `mccc_cc_std`) to `None` for the event and all its seismograms.
    ICCS CC values are not affected.

    Args:
        session: Database session.
        event: AimbatEvent whose quality should be cleared.
    """
    logger.debug(f"Clearing MCCC quality for event {event.id}.")

    if event.quality is not None:
        event.quality.mccc_rmse = None
        session.add(event.quality)

    for seis in event.seismograms:
        if seis.quality is not None:
            seis.quality.mccc_error = None
            seis.quality.mccc_cc_mean = None
            seis.quality.mccc_cc_std = None
            session.add(seis.quality)

    session.commit()


def build_iccs_from_snapshot(session: Session, snapshot_id: UUID) -> BoundICCS:
    """Build a read-only BoundICCS from a snapshot's parameters and live waveform data.

    Uses the snapshot's event and seismogram parameters (window, t1, flip, select,
    bandpass, etc.) but reads waveform data from the live datasources. Seismograms
    added after the snapshot was taken are not included in the snapshot — their live
    parameters are used instead. No DB writes occur at any point.

    Args:
        session: Database session.
        snapshot_id: ID of the AimbatSnapshot to load.

    Returns:
        BoundICCS instance built from the snapshot parameters.

    Raises:
        ValueError: If no snapshot with the given ID is found.
    """
    logger.info(f"Building ICCS from snapshot {snapshot_id}.")

    statement = (
        select(AimbatSnapshot)
        .where(AimbatSnapshot.id == snapshot_id)
        .options(
            selectinload(rel(AimbatSnapshot.event))
            .selectinload(rel(AimbatEvent.seismograms))
            .selectinload(rel(AimbatSeismogram.parameters)),
            selectinload(rel(AimbatSnapshot.event_parameters_snapshot)),
            selectinload(rel(AimbatSnapshot.seismogram_parameters_snapshots)),
        )
    )
    snapshot = session.exec(statement).one_or_none()

    if snapshot is None:
        raise ValueError(f"Snapshot {snapshot_id} not found.")

    ep = snapshot.event_parameters_snapshot
    snap_params = AimbatEventParametersBase.model_validate(ep)

    # Build a map from seismogram_parameters_id → snapshot parameters
    snap_seis_map = {
        sp.seismogram_parameters_id: sp
        for sp in snapshot.seismogram_parameters_snapshots
    }

    seismograms = []
    for seis in snapshot.event.seismograms:
        snap_sp = snap_seis_map.get(seis.parameters.id)
        if snap_sp is None:
            # Seismogram was added after the snapshot — use live parameters
            seis_params = AimbatSeismogramParametersBase.model_validate(seis.parameters)
        else:
            seis_params = AimbatSeismogramParametersBase.model_validate(snap_sp)
        seismograms.append(
            MiniIccsSeismogram(
                begin_time=seis.begin_time,
                delta=seis.delta,
                data=seis.data,
                t0=seis.t0,
                t1=seis_params.t1,
                flip=seis_params.flip,
                select=seis_params.select,
                extra={"id": seis.id},
            )
        )

    iccs = ICCS(
        seismograms=seismograms,
        window_pre=snap_params.window_pre,
        window_post=snap_params.window_post,
        ramp_width=snap_params.ramp_width,
        bandpass_apply=snap_params.bandpass_apply,
        bandpass_fmin=snap_params.bandpass_fmin,
        bandpass_fmax=snap_params.bandpass_fmax,
        min_cc=snap_params.min_cc,
        context_width=settings.context_width,
    )
    return BoundICCS(
        iccs=iccs,
        event_id=snapshot.event_id,
        created_at=Timestamp.now("UTC"),
    )


def validate_iccs_construction(
    event: AimbatEvent, parameters: AimbatEventParametersBase | None = None
) -> None:
    """Try to construct an ICCS instance for the event without caching the result.

    Use this to check whether the event's current (possibly uncommitted) parameters
    are compatible with ICCS construction before persisting them to the database.

    Args:
        event: AimbatEvent.
        parameters: Optional AimbatEventParametersBase to use instead of the live
            event parameters (useful for validation).

    Raises:
        Any exception raised by ICCS construction (e.g. invalid parameter values).
    """
    _build_iccs(event, parameters=parameters)


def _write_back_seismograms(session: Session, iccs: ICCS) -> None:
    """Write t1, flip, and select from ICCS seismograms back to the database.

    Calls `session.commit()` after writing; any other pending changes on
    `session` are also committed.

    Args:
        session: Database session.
        iccs: ICCS instance whose seismograms carry UUIDs in their extra dict.
    """
    logger.debug(f"Writing back {len(iccs.seismograms)} seismogram parameters to DB.")

    for seis in iccs.seismograms:
        db_seis = session.get(AimbatSeismogram, seis.extra["id"])
        if db_seis is not None:
            db_seis.parameters.t1 = seis.t1
            db_seis.parameters.flip = seis.flip
            db_seis.parameters.select = seis.select
    session.commit()


def sync_iccs_parameters(session: Session, event: AimbatEvent, iccs: ICCS) -> None:
    """Sync an existing ICCS instance's parameters from the database.

    Updates event-level and per-seismogram parameters without re-reading waveform
    data. Use this after operations that change parameters but not the
    seismogram list (e.g. rolling back to a snapshot).

    Args:
        session: Database session.
        event: AimbatEvent.
        iccs: ICCS instance to update in-place.
    """

    logger.debug(f"Syncing ICCS parameters from database for event {event.id}.")

    event_params = AimbatEventParametersBase.model_validate(event.parameters)
    for field_name in AimbatEventParametersBase.model_fields:
        if hasattr(iccs, field_name):
            setattr(iccs, field_name, getattr(event_params, field_name))

    for iccs_seis in iccs.seismograms:
        db_seis = session.get(AimbatSeismogram, iccs_seis.extra["id"])
        if db_seis is not None:
            seis_params = AimbatSeismogramParametersBase.model_validate(
                db_seis.parameters
            )
            for field_name in AimbatSeismogramParametersBase.model_fields:
                setattr(iccs_seis, field_name, getattr(seis_params, field_name))

    iccs.clear_cache()


def run_iccs(
    session: Session, event: AimbatEvent, iccs: ICCS, autoflip: bool, autoselect: bool
) -> IccsResult:
    """Run the Iterative Cross-Correlation and Stack (ICCS) algorithm.

    Args:
        session: Database session.
        event: AimbatEvent.
        iccs: ICCS instance.
        autoflip: If True, automatically flip seismograms to maximise cross-correlation.
        autoselect: If True, automatically deselect seismograms whose cross-correlation
            falls below the threshold.

    Returns:
        IccsResult from the algorithm run.
    """

    logger.info(f"Running ICCS (autoflip={autoflip}, autoselect={autoselect}).")

    result = iccs(autoflip=autoflip, autoselect=autoselect)
    n_iter = len(result.convergence)
    status = "converged" if result.converged else "did not converge"
    logger.info(f"ICCS {status} after {n_iter} iterations.")
    _write_back_seismograms(session, iccs)
    _write_iccs_stats(event.id, iccs)
    return result


def run_mccc(
    session: Session, event: AimbatEvent, iccs: ICCS, all_seismograms: bool
) -> McccResult:
    """Run the Multi-Channel Cross-Correlation (MCCC) algorithm.

    Args:
        session: Database session.
        event: AimbatEvent.
        iccs: ICCS instance.
        all_seismograms: If True, include deselected seismograms in the alignment.

    Returns:
        McccResult from the algorithm run.
    """

    logger.info(
        f"Running MCCC for event {event.id} (all_seismograms={all_seismograms})."
    )

    result = iccs.run_mccc(
        all_seismograms=all_seismograms,
        min_cc=event.parameters.mccc_min_cc,
        damping=event.parameters.mccc_damp,
    )
    _write_back_seismograms(session, iccs)
    _write_iccs_stats(event.id, iccs)
    _write_mccc_quality(event.id, iccs, result, all_seismograms)
    return result
