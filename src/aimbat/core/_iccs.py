"""Processing of data for AIMBAT."""

from dataclasses import dataclass
from uuid import UUID

from pandas import Timestamp
from sqlmodel import Session

from pysmo.tools.iccs import (
    ICCS,
    MiniICCSSeismogram,
)

from aimbat import settings
from aimbat.logger import logger
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatSnapshot
from aimbat.models._parameters import (
    AimbatEventParametersBase,
    AimbatSeismogramParametersBase,
)

__all__ = [
    "BoundICCS",
    "build_iccs_from_snapshot",
    "create_iccs_instance",
    "clear_iccs_cache",
    "validate_iccs_construction",
    "sync_iccs_parameters",
    "run_iccs",
    "run_mccc",
    "_write_back_seismograms",
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


def _build_iccs(event: AimbatEvent) -> ICCS:
    """Build an ICCS instance from an event's current parameters and seismograms.

    Args:
        event: AimbatEvent.

    Returns:
        A freshly constructed ICCS instance.
    """
    p = event.parameters
    seismograms = [
        MiniICCSSeismogram(
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
        bandpass_apply=p.bandpass_apply,
        bandpass_fmin=p.bandpass_fmin,
        bandpass_fmax=p.bandpass_fmax,
        min_ccnorm=p.min_ccnorm,
        context_width=settings.context_width,
    )


def create_iccs_instance(session: Session, event: AimbatEvent) -> BoundICCS:
    """Return a BoundICCS instance for the given event.

    Returns the cached instance when it is still fresh (i.e. `event.last_modified`
    has not advanced since the instance was created). Otherwise builds a new one
    and updates the cache.

    `MiniICCSSeismogram` instances are constructed directly from each
    `AimbatSeismogram`, passing `data` by reference to the read-only io cache.
    No waveform data is copied. The session does not need to remain open after
    this call.

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

    logger.info(f"Creating ICCS instance for event {event.id}.")
    bound = BoundICCS(
        iccs=_build_iccs(event),
        event_id=event.id,
        created_at=Timestamp.now("UTC"),
    )
    _iccs_cache[event.id] = bound
    return bound


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
    snapshot = session.get(AimbatSnapshot, snapshot_id)
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
            MiniICCSSeismogram(
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
        bandpass_apply=snap_params.bandpass_apply,
        bandpass_fmin=snap_params.bandpass_fmin,
        bandpass_fmax=snap_params.bandpass_fmax,
        min_ccnorm=snap_params.min_ccnorm,
        context_width=settings.context_width,
    )
    return BoundICCS(
        iccs=iccs,
        event_id=snapshot.event_id,
        created_at=Timestamp.now("UTC"),
    )


def validate_iccs_construction(event: AimbatEvent) -> None:
    """Try to construct an ICCS instance for the event without caching the result.

    Use this to check whether the event's current (possibly uncommitted) parameters
    are compatible with ICCS construction before persisting them to the database.

    Args:
        event: AimbatEvent.

    Raises:
        Any exception raised by ICCS construction (e.g. invalid parameter values).
    """
    _build_iccs(event)


def _write_back_seismograms(session: Session, iccs: ICCS) -> None:
    """Write t1, flip, and select from ICCS seismograms back to the database.

    Args:
        session: Database session.
        iccs: ICCS instance whose seismograms carry UUIDs in their extra dict.
    """
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

    logger.info(f"Syncing ICCS parameters from database for event {event.id}.")

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


def run_iccs(session: Session, iccs: ICCS, autoflip: bool, autoselect: bool) -> None:
    """Run the Iterative Cross-Correlation and Stack (ICCS) algorithm.

    Args:
        session: Database session.
        iccs: ICCS instance.
        autoflip: If True, automatically flip seismograms to maximise cross-correlation.
        autoselect: If True, automatically deselect seismograms whose cross-correlation
            falls below the threshold.
    """

    logger.info(f"Running ICCS with {autoflip=}, {autoselect=}.")

    results = iccs(autoflip=autoflip, autoselect=autoselect)
    logger.info(f"ICCS {results = }")
    _write_back_seismograms(session, iccs)


def run_mccc(
    session: Session, event: AimbatEvent, iccs: ICCS, all_seismograms: bool
) -> None:
    """Run the Multi-Channel Cross-Correlation (MCCC) algorithm.

    Args:
        session: Database session.
        event: AimbatEvent.
        iccs: ICCS instance.
        all_seismograms: If True, include deselected seismograms in the alignment.
    """

    logger.info(f"Running MCCC for event {event.id} with {all_seismograms=}.")

    iccs.run_mccc(
        all_seismograms=all_seismograms,
        min_cc=event.parameters.mccc_min_ccnorm,
        damping=event.parameters.mccc_damp,
    )
    _write_back_seismograms(session, iccs)
