"""Build and run ICCS/MCCC instances for AIMBAT phases, and track their live quality metrics.

Wraps `pysmo.tools.iccs.ICCS` with AIMBAT's database-backed phase and
seismogram parameters. `create_iccs_instance` builds (or reuses a
process-level cached) `ICCS` instance for a phase and keeps the
`iccs_cc` quality field in sync with it; `run_iccs` and `run_mccc` run
the corresponding alignment/picking algorithms and persist their
results.
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sqlalchemy import event as sa_event
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from pysmo.tools.iccs import (
    ICCS,
    IccsResult,
    IccsStatus,
    McccResult,
    MiniIccsSeismogram,
)

from aimbat import settings
from aimbat.logger import logger
from aimbat.models import (
    AimbatPhase,
    AimbatPhaseQuality,
    AimbatSeismogramParameters,
    AimbatSeismogramQuality,
    AimbatSnapshot,
)
from aimbat.models._parameters import (
    PHASE_PARAMETER_SPECS,
    SEISMOGRAM_PARAMETER_SPECS,
    AimbatPhaseParametersBase,
    AimbatSeismogramParametersBase,
)
from aimbat.utils import mean_and_sem, rel

from ._validity import compute_digests, encode_members

__all__ = [
    "BoundICCS",
    "CcStats",
    "IccsLifecycle",
    "IccsValidationError",
    "NoSeismogramsError",
    "RunSummary",
    "build_iccs_from_snapshot",
    "cc_stats",
    "clear_iccs_cache",
    "create_iccs_instance",
    "current_instance_digest",
    "evict_iccs_cache_entry",
    "ignore_run_summary_warnings",
    "run_iccs",
    "run_mccc",
    "summarise_iccs_result",
    "summarise_mccc_result",
    "sync_iccs_parameters",
    "validate_iccs_construction",
    "write_back_seismograms",
]


class IccsValidationError(ValueError):
    """Raised when a phase's parameters cannot produce an ICCS instance.

    A `ValueError` subclass, so callers that only care that the parameters
    were rejected can keep catching `ValueError`.
    """


class NoSeismogramsError(RuntimeError):
    """Raised when an ICCS instance is requested for a phase with no seismograms.

    A phase with no seismograms has no stack, so any downstream access to
    correlation values or the stack raises deep inside pysmo. Callers get
    this clear, catchable error up front instead.
    """


@dataclass
class BoundICCS:
    """An ICCS instance explicitly bound to a specific phase.

    Use `is_stale` to detect whether a parameter the instance is built from
    has changed (e.g. by a CLI command) since it was created.
    """

    iccs: ICCS
    phase_id: UUID
    instance_digest: str | None
    """Instance digest of the parameters the instance reflects. `None` when
    it does not reflect the live parameters (built from a snapshot)."""

    def is_stale(self, phase_id: UUID, instance_digest: str) -> bool:
        """Return True if this ICCS instance no longer matches the phase.

        An MCCC-only or `min_cc` change does not make it stale (`run_iccs`
        refreshes `min_cc` on the instance per run).

        Args:
            phase_id: The phase to check against.
            instance_digest: The phase's current instance digest.
        """
        return phase_id != self.phase_id or instance_digest != self.instance_digest

    def mark_current(self, session: Session) -> None:
        """Record that the instance reflects the phase's stored parameters.

        Call after writing the instance's own changes to the database.
        """
        self.instance_digest = current_instance_digest(session, self.phase_id)


def current_instance_digest(session: Session, phase_id: UUID) -> str:
    """The instance digest of the stored parameters of a phase."""
    return compute_digests(session, phase_id)[phase_id].instance


@dataclass
class IccsLifecycle:
    """Framework-agnostic state and policy for keeping a `BoundICCS` up to date.

    Owns the bound instance plus the bookkeeping needed to create it
    asynchronously without blocking a UI thread: an in-progress guard so
    overlapping creation attempts collapse into one, a one-shot retry flag
    for recovering from a transient failure, and a fallback staleness check
    (the instance digest last seen) for the window before any instance
    exists yet.

    Callers own the actual I/O and threading (reading waveform data, running
    in a background thread, marshalling results back to a UI thread) and
    call the methods here only to record the outcome. See `AimbatTUI`'s
    `_IccsLifecycleMixin` for the reference (Textual-based) caller.
    """

    bound: BoundICCS | None = None
    retry_pending: bool = False
    instance_digest_seen: str | None = None
    _creating: bool = field(default=False, repr=False, init=False)

    @property
    def ready(self) -> bool:
        """Whether a bound ICCS instance is currently available."""
        return self.bound is not None

    def is_stale(self, phase_id: UUID, instance_digest: str) -> bool:
        """Return True if the bound instance (or lack of one) needs rebuilding.

        Delegates to `BoundICCS.is_stale` when an instance exists; otherwise
        compares `instance_digest` with the one last recorded via
        `note_checked`.

        Args:
            phase_id: The phase to check against.
            instance_digest: The phase's current instance digest.
        """
        if self.bound is not None:
            return self.bound.is_stale(phase_id, instance_digest)
        return instance_digest != self.instance_digest_seen

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

        Use when creation could not even be attempted (e.g. no phase
        selected) rather than when it was attempted and failed.
        """
        self._creating = False

    def mark_failed(self, *, is_retry: bool) -> None:
        """Record a failed creation attempt.

        Args:
            is_retry: Whether this attempt was itself the one-shot retry. A
                retry is not allowed to re-arm itself, so a persistently
                failing phase gets exactly one automatic retry rather than
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
        failed creation attempt (e.g. its phase was deleted).
        """
        self.bound = None

    def note_checked(self, instance_digest: str) -> None:
        """Record the instance digest observed at a staleness check.

        Only meaningful while `bound` is `None`; used by `is_stale` to
        detect further changes before a new instance can be created.
        """
        self.instance_digest_seen = instance_digest


@dataclass(frozen=True)
class CcStats:
    """Live CC summary statistics for an ICCS instance.

    `mean_selected`/`sem_selected` are computed from seismograms with
    `select=True` only; `mean_all`/`sem_all` from every seismogram. SEM
    fields are `None` when fewer than two values are available.

    Computed directly from `ICCS.ccs` against the current stack, so it is
    always up to date without a DB round-trip. For the persisted-quality
    equivalent (phase/station/snapshot scoped, DB-backed), see
    `aimbat.models.SeismogramQualityStats`.
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
# per process). In the shell/TUI a warm entry is reused across commands,
# avoiding redundant data loading and ICCS computation. Bounded LRU (evict
# least-recently-used once full) so visiting many phases in one long-running
# process doesn't pin every phase's seismogram data in memory forever - each
# entry holds a full copy-by-reference waveform list for its phase.
_ICCS_CACHE_MAX_ENTRIES = 32
_iccs_cache: OrderedDict[UUID, BoundICCS] = OrderedDict()


def clear_iccs_cache() -> None:
    """Clear the process-level ICCS cache."""
    _iccs_cache.clear()


def evict_iccs_cache_entry(phase_id: UUID) -> None:
    """Remove one phase's cached ICCS instance, if present.

    Call this whenever a phase is deleted, so its cached waveform data
    don't linger in memory for the rest of the process on the strength of
    an ID that no longer refers to anything.

    Args:
        phase_id: ID of the deleted phase.
    """
    _iccs_cache.pop(phase_id, None)


_PENDING_KEY = "aimbat_iccs_pending"


def _evict_on_rollback(session: Session, bound: BoundICCS) -> None:
    """Drop `bound` from the cache if `session` rolls back before committing.

    The instance was built on the assumption that its flushed CC rows would be
    kept. Once they are discarded, a cache hit would skip the write that
    repopulates them.
    """
    pending: list[BoundICCS] | None = session.info.get(_PENDING_KEY)
    if pending is None:
        pending = session.info[_PENDING_KEY] = []

        def _on_rollback(_session: Session, _previous: object) -> None:
            for item in pending:
                if _iccs_cache.get(item.phase_id) is item:
                    del _iccs_cache[item.phase_id]
            pending.clear()

        def _on_commit(_session: Session) -> None:
            pending.clear()

        sa_event.listen(session, "after_soft_rollback", _on_rollback)
        sa_event.listen(session, "after_commit", _on_commit)
    pending.append(bound)


# AIMBAT parameter field name -> ICCS attribute name, for the parameters ICCS
# knows about.
_ICCS_PHASE_ATTRIBUTES = {
    name: spec.iccs_attribute
    for name, spec in PHASE_PARAMETER_SPECS.items()
    if spec.iccs_attribute is not None
}
_ICCS_SEISMOGRAM_ATTRIBUTES = {
    name: spec.iccs_attribute
    for name, spec in SEISMOGRAM_PARAMETER_SPECS.items()
    if spec.iccs_attribute is not None
}


def _phase(session: Session, phase_id: UUID) -> AimbatPhase:
    """Return the phase with ID `phase_id`.

    Raises:
        NoResultFound: If there is no such phase.
    """
    phase = session.get(AimbatPhase, phase_id)
    if phase is None:
        raise NoResultFound(f"No phase found with ID {phase_id}.")
    return phase


def _build_iccs(
    phase: AimbatPhase, parameters: AimbatPhaseParametersBase | None = None
) -> ICCS:
    """Build an ICCS instance from a phase's parameters and seismograms.

    Each ICCS seismogram carries the seismogram ID (`id`) and the ID of its
    row for the phase (`row_id`) in `extra`.

    Args:
        phase: AimbatPhase.
        parameters: Optional AimbatPhaseParametersBase to use instead of the live
            phase parameters (useful for validation).

    Returns:
        A freshly constructed ICCS instance.

    """
    p = parameters or phase.parameters
    seismograms = [
        MiniIccsSeismogram(
            begin_time=row.seismogram.begin_time,
            delta=row.seismogram.delta,
            data=row.seismogram.data,
            initial_pick=row.initial_pick,
            extra={"id": row.seismogram_id, "row_id": row.id},
            **{
                attribute: getattr(row, name)
                for name, attribute in _ICCS_SEISMOGRAM_ATTRIBUTES.items()
            },
        )
        for row in phase.seismogram_parameters
    ]
    return ICCS(
        seismograms=seismograms,
        context_width=settings.context_width,
        # Includes `min_cc`, the autoselect threshold. Baked in here and
        # refreshed per run in `run_iccs` - a bare `min_cc` change does not
        # rebuild the instance (it is not in the instance digest).
        **{
            attribute: getattr(p, name)
            for name, attribute in _ICCS_PHASE_ATTRIBUTES.items()
        },
    )


def create_iccs_instance(session: Session, phase_id: UUID) -> BoundICCS:
    """Return a BoundICCS instance for a phase.

    Returns the cached instance when it is still fresh (its instance digest
    equals that of the stored parameters). Otherwise builds a new one
    and updates the cache. Building one writes each seismogram's ICCS CC value to
    the live quality table on `session`, flushed but not committed: the caller
    decides whether those values are kept. If `session` rolls back first, the
    new instance is dropped from the cache again.

    `MiniIccsSeismogram` instances are constructed directly from each
    `AimbatSeismogram`, passing `data` by reference to the read-only io cache.
    No waveform data are copied.

    Args:
        session: Database session.
        phase_id: ID of the phase.

    Returns:
        BoundICCS instance tied to the phase.

    Raises:
        NoResultFound: If the phase does not exist.
        NoSeismogramsError: If the phase has no seismograms.
    """
    _phase(session, phase_id)
    instance_digest = current_instance_digest(session, phase_id)
    cached = _iccs_cache.get(phase_id)
    if cached is not None and not cached.is_stale(phase_id, instance_digest):
        logger.debug(f"Returning cached BoundICCS for phase {phase_id}.")
        _iccs_cache.move_to_end(phase_id)
        return cached

    # pysqlite runs SELECTs outside a transaction, so objects already in the
    # identity map can be older than the rows the digest was computed from.
    phase = session.exec(
        select(AimbatPhase)
        .where(AimbatPhase.id == phase_id)
        .options(
            selectinload(rel(AimbatPhase.parameters)),
            selectinload(rel(AimbatPhase.seismogram_parameters)).selectinload(
                rel(AimbatSeismogramParameters.seismogram)
            ),
            selectinload(rel(AimbatPhase.seismogram_parameters)).selectinload(
                rel(AimbatSeismogramParameters.pick)
            ),
        )
        .execution_options(populate_existing=True)
    ).one()

    if not phase.seismogram_parameters:
        raise NoSeismogramsError(
            f"Phase {phase.name} of event {phase.event_id} has no seismograms; "
            + "cannot build an ICCS instance."
        )

    logger.debug(f"Creating ICCS instance for phase {phase_id}.")
    bound = BoundICCS(
        iccs=_build_iccs(phase),
        phase_id=phase_id,
        instance_digest=instance_digest,
    )
    # Cache only after the stats write succeeds: a half-initialised instance
    # left in the cache would be returned (without re-raising) on the next
    # call and blow up later on first stack access.
    _write_iccs_stats(session, phase_id, bound.iccs)
    _iccs_cache[phase_id] = bound
    _iccs_cache.move_to_end(phase_id)
    _evict_on_rollback(session, bound)
    if len(_iccs_cache) > _ICCS_CACHE_MAX_ENTRIES:
        _iccs_cache.popitem(last=False)
    return bound


def _find_seismogram_quality(
    session: Session, row_id: UUID
) -> AimbatSeismogramQuality | None:
    """Look up the live quality of a seismogram's row, if one exists."""
    return session.exec(
        select(AimbatSeismogramQuality).where(
            col(AimbatSeismogramQuality.seismogram_parameters_id) == row_id
        )
    ).one_or_none()


def _write_iccs_stats(session: Session, phase_id: UUID, iccs: ICCS) -> None:
    """Upsert per-seismogram ICCS CC values into the live quality table.

    Iterates over the seismograms in the ICCS instance and writes (or
    overwrites) the Pearson cross-correlation coefficient for each one, preserving
    any existing MCCC fields.

    Writes on the caller's session and flushes, so the values are part of
    whatever transaction the caller is running and are discarded with it if
    the caller rolls back. Each value is stamped with the digest of the stored
    parameters, so the parameters must match `iccs` when this is called.

    Args:
        session: Database session.
        phase_id: ID of the phase whose rows are being updated.
        iccs: ICCS instance whose `ccs` values are written.
    """
    logger.debug(f"Writing ICCS stats for phase {phase_id}.")
    digests = compute_digests(session, phase_id)[phase_id]
    for iccs_seis, cc in zip(iccs.seismograms, iccs.ccs):
        row_id = iccs_seis.extra["row_id"]
        existing = _find_seismogram_quality(session, row_id)
        cc_val = max(-1.0, min(1.0, float(cc)))
        fingerprint = digests.seismogram_cc[row_id]
        if existing is None:
            row = AimbatSeismogramQuality(
                id=uuid4(),
                seismogram_parameters_id=row_id,
                iccs_cc=cc_val,
                iccs_fingerprint=fingerprint,
            )
            session.add(row)
        else:
            existing.iccs_cc = cc_val
            existing.iccs_fingerprint = fingerprint
            session.add(existing)
    session.flush()


def _write_mccc_quality(
    session: Session,
    phase_id: UUID,
    iccs: ICCS,
    result: McccResult,
) -> None:
    """Write MCCC quality results to the live quality tables.

    Upserts the phase-level RMSE, clears MCCC fields for all seismograms in
    the ICCS instance, then writes the per-seismogram metrics for the seismograms
    that were actually used in the inversion. A seismogram whose MCCC shift was
    refused keeps its previous pick, so its error is stored as `NULL` rather
    than the error of the pick it did not receive. The `iccs_cc` field is preserved
    when an existing quality row is found; seismograms with no prior quality row
    will have `iccs_cc = NULL` until ICCS stats are written separately.

    Writes on the caller's session and flushes, so the values are part of
    whatever transaction the caller is running and are discarded with it if
    the caller rolls back. The results are stamped with the digest of the
    stored parameters, so the picks must have been written back first.

    Args:
        session: Database session.
        phase_id: ID of the phase that was processed.
        iccs: ICCS instance used for the MCCC run.
        result: McccResult returned by `ICCS.run_mccc`.
    """
    logger.debug(f"Writing MCCC quality for phase {phase_id}.")
    members = {iccs.seismograms[index].extra["row_id"] for index in result.indices}
    fingerprint = compute_digests(session, phase_id)[phase_id].mccc(members)
    existing_eq = session.exec(
        select(AimbatPhaseQuality).where(col(AimbatPhaseQuality.phase_id) == phase_id)
    ).one_or_none()
    if existing_eq is None:
        existing_eq = AimbatPhaseQuality(id=uuid4(), phase_id=phase_id)
    existing_eq.mccc_rmse = result.rmse
    existing_eq.mccc_members = encode_members(members)
    existing_eq.mccc_fingerprint = fingerprint
    session.add(existing_eq)

    # Clear MCCC fields for all seismograms first
    for iccs_seis in iccs.seismograms:
        sq = _find_seismogram_quality(session, iccs_seis.extra["row_id"])
        if sq is not None:
            sq.mccc_error = None
            sq.mccc_cc_mean = None
            sq.mccc_cc_std = None
            sq.mccc_refused = None
            session.add(sq)

    # Write MCCC metrics for used seismograms. CC values are clamped to
    # their valid ranges (mean [0, 1], std >= 0) to absorb floating-point
    # overshoot, matching `_write_iccs_stats`: table models skip the
    # Pydantic bounds so nothing else enforces them here.
    for index, error, cc_mean, cc_std in zip(
        result.indices, result.errors, result.cc_means, result.cc_stds, strict=True
    ):
        row_id = iccs.seismograms[index].extra["row_id"]
        refused = index in result.refused
        if refused:
            error = None
        cc_mean_val = max(0.0, min(1.0, float(cc_mean)))
        cc_std_val = max(0.0, float(cc_std))
        sq = _find_seismogram_quality(session, row_id)
        if sq is None:
            sq = AimbatSeismogramQuality(
                id=uuid4(),
                seismogram_parameters_id=row_id,
                mccc_error=error,
                mccc_cc_mean=cc_mean_val,
                mccc_cc_std=cc_std_val,
                mccc_refused=refused,
            )
            session.add(sq)
        else:
            sq.mccc_error = error
            sq.mccc_cc_mean = cc_mean_val
            sq.mccc_cc_std = cc_std_val
            sq.mccc_refused = refused
            session.add(sq)

    session.flush()


def build_iccs_from_snapshot(session: Session, snapshot_id: UUID) -> BoundICCS:
    """Build a read-only BoundICCS from a snapshot's parameters and live waveform data.

    Uses the snapshot's phase and seismogram parameters (window, refined pick, flip, select,
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
            selectinload(rel(AimbatSnapshot.phase))
            .selectinload(rel(AimbatPhase.seismogram_parameters))
            .selectinload(rel(AimbatSeismogramParameters.seismogram)),
            selectinload(rel(AimbatSnapshot.phase_parameters_snapshot)),
            selectinload(rel(AimbatSnapshot.seismogram_parameters_snapshots)),
        )
    )
    snapshot = session.exec(statement).one_or_none()

    if snapshot is None:
        raise ValueError(f"Snapshot {snapshot_id} not found.")

    ep = snapshot.phase_parameters_snapshot
    snap_params = AimbatPhaseParametersBase.model_validate(ep)

    # Build a map from seismogram_id → snapshot parameters
    snap_seis_map = {
        sp.seismogram_id: sp for sp in snapshot.seismogram_parameters_snapshots
    }

    seismograms = []
    for row in snapshot.phase.seismogram_parameters:
        seis = row.seismogram
        snap_sp = snap_seis_map.get(seis.id)
        if snap_sp is None:
            # Seismogram was added after the snapshot: use live parameters
            seis_params = AimbatSeismogramParametersBase.model_validate(row)
        else:
            seis_params = AimbatSeismogramParametersBase.model_validate(snap_sp)
        seismograms.append(
            MiniIccsSeismogram(
                begin_time=seis.begin_time,
                delta=seis.delta,
                data=seis.data,
                initial_pick=row.initial_pick,
                refined_pick=seis_params.refined_pick,
                flip=seis_params.flip,
                select=seis_params.select,
                extra={"id": seis.id, "row_id": row.id},
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
        phase_id=snapshot.phase_id,
        instance_digest=None,
    )


def validate_iccs_construction(
    phase: AimbatPhase, parameters: AimbatPhaseParametersBase | None = None
) -> None:
    """Try to construct an ICCS instance for the phase without caching the result.

    Use this to check whether the phase's current (possibly uncommitted) parameters
    are compatible with ICCS construction before persisting them to the database.

    Args:
        phase: AimbatPhase.
        parameters: Optional AimbatPhaseParametersBase to use instead of the live
            phase parameters (useful for validation).

    Raises:
        IccsValidationError: If the parameters are rejected by ICCS construction.
    """
    try:
        _build_iccs(phase, parameters=parameters)
    except ValueError as exc:
        # pysmo's attrs validators and pydantic both reject bad parameter
        # values with a ValueError. Anything else - a missing data source, an
        # AttributeError - is not the parameters' fault and propagates as
        # itself rather than being relabelled.
        logger.exception("ICCS validation failed during parameter check.")
        raise IccsValidationError(f"ICCS validation failed: {exc}") from exc


def write_back_seismograms(session: Session, iccs: ICCS) -> None:
    """Write refined_pick, flip, and select from ICCS seismograms back to the database.

    Flushes but does not commit; the caller owns the transaction and must
    commit it. If `iccs` is cached and matched the stored parameters before
    the write, its cached digest is updated to match them again.

    Args:
        session: Database session.
        iccs: ICCS instance whose seismograms carry UUIDs in their extra dict.
    """
    logger.debug(f"Writing back {len(iccs.seismograms)} seismogram parameters to DB.")

    bound = next((b for b in _iccs_cache.values() if b.iccs is iccs), None)
    was_current = bound is not None and not bound.is_stale(
        bound.phase_id, current_instance_digest(session, bound.phase_id)
    )

    for seis in iccs.seismograms:
        row = session.get(AimbatSeismogramParameters, seis.extra["row_id"])
        if row is not None:
            for name, attribute in _ICCS_SEISMOGRAM_ATTRIBUTES.items():
                setattr(row, name, getattr(seis, attribute))
    session.flush()

    if bound is not None and was_current:
        bound.mark_current(session)


def sync_iccs_parameters(session: Session, phase_id: UUID, iccs: ICCS) -> None:
    """Sync an existing ICCS instance's parameters from the database.

    Updates phase-level and per-seismogram parameters without re-reading waveform
    data. Use this after operations that change parameters but not the
    seismogram list (e.g. rolling back to a snapshot).

    Args:
        session: Database session.
        phase_id: ID of the phase the instance belongs to.
        iccs: ICCS instance to update in-place.
    """

    logger.debug(f"Syncing ICCS parameters from database for phase {phase_id}.")

    phase_params = AimbatPhaseParametersBase.model_validate(
        _phase(session, phase_id).parameters
    )
    for name, attribute in _ICCS_PHASE_ATTRIBUTES.items():
        setattr(iccs, attribute, getattr(phase_params, name))

    for iccs_seis in iccs.seismograms:
        row = session.get(AimbatSeismogramParameters, iccs_seis.extra["row_id"])
        if row is not None:
            seis_params = AimbatSeismogramParametersBase.model_validate(row)
            for name, attribute in _ICCS_SEISMOGRAM_ATTRIBUTES.items():
                setattr(iccs_seis, attribute, getattr(seis_params, name))

    iccs.clear_cache()


@dataclass(frozen=True)
class RunSummary:
    """A one-paragraph account of an ICCS or MCCC run for the user."""

    message: str
    """What the run did, in full sentences."""

    warning: bool
    """Whether the outcome needs the user's attention."""


_WINDOW_DOES_NOT_FIT = (
    "the time window (including its taper ramp) would extend beyond the data"
)


def ignore_run_summary_warnings() -> None:
    """Ignore the pysmo warnings that a `RunSummary` already reports.

    Covers refused ICCS and MCCC shifts and the autoselect fallback. Adds a
    process-wide filter, so call it inside `warnings.catch_warnings()` and
    before any thread that runs ICCS or MCCC starts.
    """
    import warnings

    warnings.filterwarnings(
        "ignore",
        message=r"(ICCS|MCCC) refused|autoselect left no seismograms",
        category=UserWarning,
    )


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def summarise_iccs_result(result: IccsResult, n_seismograms: int) -> RunSummary:
    """Describe the outcome of an ICCS run.

    Args:
        result: Result returned by the ICCS run.
        n_seismograms: Number of seismograms in the ICCS instance.

    Returns:
        The summary, flagged as a warning when the run did not converge, moved
        no picks, refused any pick, or had to keep a seismogram selected.
    """
    iterations = _plural(len(result.convergence), "iteration")
    if result.status is IccsStatus.nothing_applied:
        sentences = [
            f"ICCS moved no picks in {iterations} because, for every "
            + f"seismogram, {_WINDOW_DOES_NOT_FIT}. Shorten the time window "
            + "or the taper ramp."
        ]
    else:
        if result.status is IccsStatus.converged:
            sentences = [f"ICCS converged after {iterations}."]
        else:
            sentences = [f"ICCS did not converge after {iterations}."]
        if result.refused:
            n_refused = len(result.refused)
            sentences.append(
                f"In the final iteration, {n_refused} of "
                + f"{_plural(n_seismograms, 'pick')} could not be updated "
                + f"because {_WINDOW_DOES_NOT_FIT}."
            )

    changes = [
        f"{len(indices)} {label}"
        for label, indices in (
            ("flipped", result.flipped),
            ("deselected", result.deselected),
            ("reselected", result.reselected),
        )
        if indices
    ]
    if changes:
        sentences.append(f"Seismograms changed: {', '.join(changes)}.")
    if result.fallback is not None:
        sentences.append(
            "Autoselect would have deselected every seismogram, so the "
            + "best-correlating one was kept selected."
        )

    warning = (
        result.status is not IccsStatus.converged
        or bool(result.refused)
        or result.fallback is not None
    )
    return RunSummary(" ".join(sentences), warning)


def summarise_mccc_result(result: McccResult) -> RunSummary:
    """Describe the outcome of an MCCC run.

    Args:
        result: Result returned by the MCCC run.

    Returns:
        The summary, flagged as a warning when any pick was not refined.
    """
    n_used = len(result.indices)
    n_refused = len(result.refused)
    if not n_refused:
        return RunSummary(f"MCCC refined {_plural(n_used, 'pick')}.", False)
    return RunSummary(
        f"MCCC refined {n_used - n_refused} of {_plural(n_used, 'pick')}. "
        + f"{n_refused} {'was' if n_refused == 1 else 'were'} left unchanged "
        + f"because {_WINDOW_DOES_NOT_FIT}.",
        True,
    )


def _log_summary(
    summary: RunSummary, iccs: ICCS, groups: dict[str, frozenset[int]]
) -> None:
    """Log a run summary, then the IDs of the seismograms in each group."""
    logger.log("WARNING" if summary.warning else "INFO", summary.message)
    for label, indices in groups.items():
        if indices:
            ids = ", ".join(
                str(iccs.seismograms[i].extra["id"]) for i in sorted(indices)
            )
            logger.info(f"{label}: {ids}")


def run_iccs(
    session: Session, phase_id: UUID, iccs: ICCS, autoflip: bool, autoselect: bool
) -> IccsResult:
    """Run the Iterative Cross-Correlation and Stack (ICCS) algorithm.

    Args:
        session: Database session.
        phase_id: ID of the phase the instance belongs to.
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
    iccs.min_cc = _phase(session, phase_id).parameters.min_cc
    result = iccs(autoflip=autoflip, autoselect=autoselect)
    _log_summary(
        summarise_iccs_result(result, len(iccs.seismograms)),
        iccs,
        {
            "ICCS refused picks": result.refused,
            "ICCS flipped": result.flipped,
            "ICCS deselected": result.deselected,
            "ICCS reselected": result.reselected,
        },
    )
    # ICCS writes its own inputs, so the results are stamped after the picks
    # are written back.
    write_back_seismograms(session, iccs)
    _write_iccs_stats(session, phase_id, iccs)
    session.flush()
    return result


def run_mccc(
    session: Session, phase_id: UUID, iccs: ICCS, all_seismograms: bool
) -> McccResult:
    """Run the Multi-Channel Cross-Correlation (MCCC) algorithm.

    Args:
        session: Database session.
        phase_id: ID of the phase the instance belongs to.
        iccs: ICCS instance.
        all_seismograms: If True, include deselected seismograms in the alignment.

    Returns:
        McccResult from the algorithm run.
    """

    logger.info(
        f"Running MCCC for phase {phase_id} (all_seismograms={all_seismograms})."
    )

    parameters = _phase(session, phase_id).parameters
    result = iccs.run_mccc(
        all_seismograms=all_seismograms,
        min_cc=parameters.mccc_min_cc,
        damping=parameters.mccc_damp,
    )
    _log_summary(
        summarise_mccc_result(result), iccs, {"MCCC refused picks": result.refused}
    )
    # MCCC writes its own inputs, so the results are stamped after the picks
    # are written back.
    write_back_seismograms(session, iccs)
    _write_iccs_stats(session, phase_id, iccs)
    _write_mccc_quality(session, phase_id, iccs, result)
    session.flush()
    return result
