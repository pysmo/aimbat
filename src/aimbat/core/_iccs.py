"""Build and run ICCS/MCCC instances for AIMBAT events, and track their live quality metrics.

Wraps `pysmo.tools.iccs.ICCS` with AIMBAT's database-backed event and
seismogram parameters. `create_iccs_instance` builds (or reuses a
process-level cached) `ICCS` instance for an event and keeps the
`iccs_cc` quality field in sync with it; `run_iccs` and `run_mccc` run
the corresponding alignment/picking algorithms and persist their
results.
"""

from dataclasses import dataclass, field
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
    AimbatEventQuality,
    AimbatSeismogram,
    AimbatSeismogramQuality,
    AimbatSnapshot,
)
from aimbat.models._parameters import (
    AimbatEventParametersBase,
    AimbatSeismogramParametersBase,
)
from aimbat.utils import mean_and_sem, rel

__all__ = [
    "BoundICCS",
    "CcStats",
    "IccsLifecycle",
    "build_iccs_from_snapshot",
    "cc_stats",
    "clear_iccs_cache",
    "clear_mccc_quality",
    "create_iccs_instance",
    "run_iccs",
    "run_mccc",
    "sync_iccs_parameters",
    "validate_iccs_construction",
    "write_back_seismograms",
]


@dataclass
class BoundICCS:
    """An ICCS instance explicitly bound to a specific event.

    Use `is_stale` to detect whether a stack-affecting parameter has been
    modified (e.g. by a CLI command) since this instance was created.
    """

    iccs: ICCS
    event_id: UUID
    created_at: Timestamp

    def is_stale(self, event: AimbatEvent) -> bool:
        """Return True if this ICCS instance no longer matches the event.

        Args:
            event: The event to check against.

        Returns:
            True if `event.id` differs from the bound event, or if
            `event.stack_modified` has advanced since this instance was
            created. An MCCC-only or `min_cc` change does not make it stale
            (`run_iccs` refreshes `min_cc` on the instance per run).
        """
        if event.id != self.event_id:
            return True
        if event.stack_modified is None:
            return False
        return event.stack_modified > self.created_at


@dataclass
class IccsLifecycle:
    """Framework-agnostic state and policy for keeping a `BoundICCS` up to date.

    Owns the bound instance plus the bookkeeping needed to create it
    asynchronously without blocking a UI thread: an in-progress guard so
    overlapping creation attempts collapse into one, a one-shot retry flag
    for recovering from a transient failure, and a fallback staleness check
    (`event.stack_modified`) for the window before any instance exists yet.

    Callers own the actual I/O and threading (reading waveform data, running
    in a background thread, marshalling results back to a UI thread) and
    call the methods here only to record the outcome. See `AimbatTUI`'s
    `_IccsLifecycleMixin` for the reference (Textual-based) caller.
    """

    bound: BoundICCS | None = None
    retry_pending: bool = False
    stack_modified_seen: Timestamp | None = None
    _creating: bool = field(default=False, repr=False, init=False)

    @property
    def ready(self) -> bool:
        """Whether a bound ICCS instance is currently available."""
        return self.bound is not None

    def is_stale(self, event: AimbatEvent) -> bool:
        """Return True if the bound instance (or lack of one) needs rebuilding.

        Delegates to `BoundICCS.is_stale` when an instance exists; otherwise
        falls back to comparing `event.stack_modified` against the value last
        recorded via `note_checked`.

        Args:
            event: The event to check against.
        """
        if self.bound is not None:
            return self.bound.is_stale(event)
        return event.stack_modified != self.stack_modified_seen

    def start_creating(self) -> bool:
        """Begin a creation attempt, discarding any existing bound instance.

        Returns:
            False if a creation attempt is already in progress, in which
            case the caller should skip starting a new one.
        """
        if self._creating:
            return False
        self._creating = True
        self.bound = None
        self.retry_pending = False
        return True

    def mark_aborted(self) -> None:
        """Clear the in-progress flag without arming a retry.

        Use when creation could not even be attempted (e.g. no event
        selected) rather than when it was attempted and failed.
        """
        self._creating = False

    def mark_failed(self, *, is_retry: bool) -> None:
        """Record a failed creation attempt.

        Args:
            is_retry: Whether this attempt was itself the one-shot retry. A
                retry is not allowed to re-arm itself, so a persistently
                failing event gets exactly one automatic retry rather than
                retrying forever.
        """
        self._creating = False
        if not is_retry:
            self.retry_pending = True

    def assign(self, bound_iccs: BoundICCS) -> None:
        """Record a newly created instance as ready."""
        self._creating = False
        self.bound = bound_iccs

    def clear(self) -> None:
        """Discard the bound instance without arming a retry.

        Use when the instance is invalidated by something other than a
        failed creation attempt (e.g. its event was deleted).
        """
        self.bound = None

    def note_checked(self, stack_modified: Timestamp | None) -> None:
        """Record the `stack_modified` value observed at a staleness check.

        Only meaningful while `bound` is `None`; used by `is_stale` to
        detect further changes before a new instance can be created.
        """
        self.stack_modified_seen = stack_modified


@dataclass(frozen=True)
class CcStats:
    """Live CC summary statistics for an ICCS instance.

    `mean_selected`/`sem_selected` are computed from seismograms with
    `select=True` only; `mean_all`/`sem_all` from every seismogram. SEM
    fields are `None` when fewer than two values are available.
    """

    n_all: int
    mean_all: float | None
    sem_all: float | None
    n_selected: int
    mean_selected: float | None
    sem_selected: float | None


def cc_stats(iccs: ICCS) -> CcStats:
    """Summarise live CC values (mean ± SEM) across all and selected seismograms.

    Uses `ICCS.ccs`, which correlates each seismogram against the current
    stack, so results are always up to date without requiring `iccs()` to
    have been called first.

    Args:
        iccs: ICCS instance.

    Returns:
        CcStats summarising the live CC values.
    """
    ccs = [float(cc) for cc in iccs.ccs]
    selected_ccs = [cc for cc, seis in zip(ccs, iccs.seismograms) if seis.select]
    mean_all, sem_all = mean_and_sem(ccs)
    mean_selected, sem_selected = mean_and_sem(selected_ccs)
    return CcStats(
        n_all=len(ccs),
        mean_all=mean_all,
        sem_all=sem_all,
        n_selected=len(selected_ccs),
        mean_selected=mean_selected,
        sem_selected=sem_selected,
    )


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
            t1=seis.parameters.t1,
            flip=seis.parameters.flip,
            select=seis.parameters.select,
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
        corners=p.corners,
        # The autoselect threshold. Baked in here and refreshed per run in
        # `run_iccs` - a bare `min_cc` change does not rebuild the instance
        # (it does not touch the stack; see trigger 1b in core/_project.py).
        min_cc=p.min_cc,
        context_width=settings.context_width,
    )


def create_iccs_instance(session: Session, event: AimbatEvent) -> BoundICCS:
    """Return a BoundICCS instance for the given event.

    Returns the cached instance when it is still fresh (i.e. `event.stack_modified`
    has not advanced since the instance was created). Otherwise builds a new one
    and updates the cache. ICCS CC values are written to the live quality table in
    a separate session so the caller's session is not affected.

    `MiniIccsSeismogram` instances are constructed directly from each
    `AimbatSeismogram`, passing `data` by reference to the read-only io cache.
    No waveform data are copied.

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

    # Stamp before reading the event's parameters and waveforms below, so a
    # modification committed while this instance is being built is caught as
    # stale on the next check rather than silently baked in.
    created_at = Timestamp.now("UTC")

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
        created_at=created_at,
    )
    _iccs_cache[event.id] = bound
    _write_iccs_stats(event.id, bound.iccs)
    return bound


def _find_seismogram_quality(
    write_session: Session, seismogram_id: UUID
) -> AimbatSeismogramQuality | None:
    """Look up a seismogram's live quality row by seismogram ID, if one exists."""
    return write_session.exec(
        select(AimbatSeismogramQuality).where(
            col(AimbatSeismogramQuality.seismogram_id) == seismogram_id
        )
    ).one_or_none()


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

    logger.debug(f"Writing ICCS stats for event {event_id}.")
    with Session(_engine) as write_session:
        for iccs_seis, cc in zip(iccs.seismograms, iccs.ccs):
            seis_id = iccs_seis.extra["id"]
            existing = _find_seismogram_quality(write_session, seis_id)
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

    used_seis = (
        iccs.seismograms
        if all_seismograms
        else [s for s in iccs.seismograms if s.select]
    )

    n_used = len(used_seis)
    if not len(result.errors) == len(result.cc_means) == len(result.cc_stds) == n_used:
        raise RuntimeError(
            f"MCCC returned {len(result.errors)} error / {len(result.cc_means)} "
            f"cc_mean / {len(result.cc_stds)} cc_std values for {n_used} "
            "seismograms; per-seismogram metrics cannot be attributed. The "
            "pysmo MCCC result is expected to align 1:1 with the used seismograms."
        )

    logger.debug(f"Writing MCCC quality for event {event_id}.")
    with Session(_engine) as write_session:
        # Event quality
        existing_eq = write_session.exec(
            select(AimbatEventQuality).where(
                col(AimbatEventQuality.event_id) == event_id
            )
        ).one_or_none()
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
            sq = _find_seismogram_quality(write_session, seis_id)
            if sq is not None:
                sq.mccc_error = None
                sq.mccc_cc_mean = None
                sq.mccc_cc_std = None
                write_session.add(sq)

        # Write MCCC metrics for used seismograms. CC values are clamped to
        # their valid ranges (mean [0, 1], std >= 0) to absorb floating-point
        # overshoot, matching `_write_iccs_stats`: table models skip the
        # Pydantic bounds so nothing else enforces them here.
        for iccs_seis, error, cc_mean, cc_std in zip(
            used_seis, result.errors, result.cc_means, result.cc_stds, strict=True
        ):
            seis_id = iccs_seis.extra["id"]
            cc_mean_val = max(0.0, min(1.0, float(cc_mean)))
            cc_std_val = max(0.0, float(cc_std))
            sq = _find_seismogram_quality(write_session, seis_id)
            if sq is None:
                sq = AimbatSeismogramQuality(
                    id=uuid4(),
                    seismogram_id=seis_id,
                    mccc_error=error,
                    mccc_cc_mean=cc_mean_val,
                    mccc_cc_std=cc_std_val,
                )
                write_session.add(sq)
            else:
                sq.mccc_error = error
                sq.mccc_cc_mean = cc_mean_val
                sq.mccc_cc_std = cc_std_val
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
    added after the snapshot was taken are not included in the snapshot; their live
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

    # Build a map from seismogram_id → snapshot parameters
    snap_seis_map = {
        sp.seismogram_id: sp for sp in snapshot.seismogram_parameters_snapshots
    }

    seismograms = []
    for seis in snapshot.event.seismograms:
        snap_sp = snap_seis_map.get(seis.id)
        if snap_sp is None:
            # Seismogram was added after the snapshot: use live parameters
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
        corners=snap_params.corners,
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
        Exception: Any exception raised by ICCS construction (e.g. invalid parameter values).
    """
    _build_iccs(event, parameters=parameters)


def write_back_seismograms(session: Session, iccs: ICCS) -> None:
    """Write t1, flip, and select from ICCS seismograms back to the database.

    Flushes but does not commit; the caller owns the transaction and must
    commit it. The flush fires the quality-invalidation triggers (SQLite
    AFTER UPDATE triggers run at statement execution), but callers that
    repopulate quality afterwards (some from their own separate sessions)
    depend on controlling when that nulling becomes visible.

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
    session.flush()


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

    # `min_cc` is stored on the instance at construction and, unlike the MCCC
    # parameters, is not re-read per call. A bare `min_cc` change does not
    # rebuild the instance (it does not affect the stack), so refresh it here
    # before an autoselect run picks up a stale threshold.
    iccs.min_cc = event.parameters.min_cc
    result = iccs(autoflip=autoflip, autoselect=autoselect)
    n_iter = len(result.convergence)
    status = "converged" if result.converged else "did not converge"
    logger.info(f"ICCS {status} after {n_iter} iterations.")
    # Writing the picks back nulls `iccs_cc` via the invalidation triggers, so
    # `_write_iccs_stats` - which runs in its own session - must come after the
    # commit to repopulate it (see `run_mccc` for the fuller ordering note).
    write_back_seismograms(session, iccs)
    session.commit()
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
    # Order is load-bearing. Writing back `t1`/`flip`/`select` fires the
    # quality-invalidation triggers that null `iccs_cc` and every MCCC quality
    # column for this event; the commit makes that visible to other sessions.
    # `_write_iccs_stats` must then repopulate `iccs_cc`, and
    # `_write_mccc_quality` the MCCC columns, in that sequence - both run in
    # their own sessions. Reordering the calls (or a failure between them)
    # leaves the quality tables half-nulled with no way to recover the missing
    # half short of re-running the algorithm.
    write_back_seismograms(session, iccs)
    session.commit()
    _write_iccs_stats(event.id, iccs)
    _write_mccc_quality(event.id, iccs, result, all_seismograms)
    return result
