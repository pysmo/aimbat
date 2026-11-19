"""Create, restore, and query AIMBAT snapshots of processing parameters and quality metrics.

A snapshot freezes a copy of the live parameters of a phase and its
seismograms, and their valid live quality metrics
(`AimbatSeismogramQuality.iccs_cc` and the MCCC diagnostics), for later
inspection or rollback.

A snapshot records two digests of the parameters (see `core._validity`):
`iccs_hash` is the phase's instance digest and `mccc_hash` the MCCC digest
of the run it froze. Live quality that no longer matches the parameters can
be restored from a snapshot whose digests match them (`resync_quality`).
"""

from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any, NamedTuple
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from aimbat.logger import logger
from aimbat.models import (
    AimbatPhase,
    AimbatPhaseParametersSnapshot,
    AimbatPhaseQuality,
    AimbatPhaseQualitySnapshot,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersSnapshot,
    AimbatSeismogramQuality,
    AimbatSeismogramQualitySnapshot,
    AimbatSnapshot,
    AimbatSnapshotRead,
    SeismogramQualityStats,
    SnapshotResults,
    SnapshotSeismogramResult,
    undefer_counts,
)
from aimbat.models._parameters import (
    AimbatPhaseParametersBase,
    AimbatSeismogramParametersBase,
)
from aimbat.models._quality import (
    AimbatPhaseQualityBase,
    AimbatSeismogramQualityBase,
)
from aimbat.utils import check_field_name_flags, dump_models, rel

from ._session import flush_deletes
from ._validity import PhaseDigests, Validity

__all__ = [
    "RollbackResult",
    "SyncResult",
    "create_snapshot",
    "create_snapshots_for_added_data",
    "delete_snapshot",
    "dump_phase_parameter_snapshot_table",
    "dump_phase_quality_snapshot_table",
    "dump_seismogram_parameter_snapshot_table",
    "dump_seismogram_quality_snapshot_table",
    "dump_snapshot_quality_table",
    "dump_snapshot_results",
    "dump_snapshot_table",
    "get_snapshot_quality",
    "get_snapshots",
    "resync_quality",
    "rollback_to_snapshot",
]


class SyncResult(NamedTuple):
    """Which live quality metrics `resync_quality` restored from a snapshot."""

    mccc_synced: bool
    iccs_synced: bool


# Every seismogram-level quality field except `iccs_cc` is an MCCC diagnostic.
_MCCC_SEISMOGRAM_QUALITY_FIELDS = tuple(
    k for k in AimbatSeismogramQualityBase.model_fields if k != "iccs_cc"
)


class RollbackResult(NamedTuple):
    """What `rollback_to_snapshot` left as it was."""

    added_since: tuple[UUID, ...]
    """IDs of the seismograms whose rows in the phase were created after the
    snapshot. Their parameters are kept as they are."""


def create_snapshot(
    session: Session,
    phase_id: UUID,
    comment: str | None = None,
    automatic: bool = False,
) -> None:
    """Create a snapshot of the AIMBAT processing parameters and quality metrics.

    Parameter snapshots are always created. Quality snapshots are created
    whenever the corresponding live quality record has at least one valid
    value. A value that no longer matches the parameters is frozen as `None`.

    Args:
        session: Database session.
        phase_id: ID of the phase.
        comment: Optional comment.
        automatic: Whether this snapshot was created automatically, e.g. by
            `data add`, rather than explicitly by the user.

    Raises:
        NoResultFound: If the phase does not exist.
    """

    logger.info(
        f"Creating snapshot for phase {phase_id}"
        + (f" with comment '{comment}'" if comment else "")
        + "."
    )

    phase = session.exec(
        select(AimbatPhase)
        .where(AimbatPhase.id == phase_id)
        .options(
            selectinload(rel(AimbatPhase.parameters)),
            selectinload(rel(AimbatPhase.quality)),
            selectinload(rel(AimbatPhase.seismogram_parameters)).selectinload(
                rel(AimbatSeismogramParameters.quality)
            ),
        )
    ).one_or_none()
    if phase is None:
        raise NoResultFound(f"No phase found with ID {phase_id}.")
    validity = Validity.read(session, phase_id)

    phase_parameters_snapshot = AimbatPhaseParametersSnapshot.model_validate(
        phase.parameters,
        update={
            "id": uuid4(),  # we don't want to carry over the id from the input phase parameters
            "parameters_id": phase.parameters.id,
        },
    )
    logger.debug(
        f"Adding phase parameters snapshot with id={phase_parameters_snapshot.id} to snapshot."
    )

    seismogram_parameter_snapshots = []
    for row in phase.seismogram_parameters:
        seismogram_parameter_snapshot = AimbatSeismogramParametersSnapshot.model_validate(
            row,
            update={
                "id": uuid4(),  # we don't want to carry over the id from the input seismogram parameters
                "seismogram_id": row.seismogram_id,
                "seismogram_parameters_id": row.id,
            },
        )
        logger.debug(
            f"Adding seismogram parameters snapshot with id={seismogram_parameter_snapshot.id} to snapshot."
        )
        seismogram_parameter_snapshots.append(seismogram_parameter_snapshot)

    # Capture quality metrics from the live quality tables.
    event_quality_snap: AimbatPhaseQualitySnapshot | None = None
    seis_quality_snaps: list[AimbatSeismogramQualitySnapshot] = []

    mccc_valid = validity.mccc(phase.id)
    if mccc_valid and phase.quality is not None and phase.quality.mccc_rmse is not None:
        logger.debug("Capturing phase quality snapshot from live quality table.")
        event_quality_snap = AimbatPhaseQualitySnapshot.model_validate(
            phase.quality,
            update={
                "id": uuid4(),
                "phase_quality_id": phase.quality.id,
            },
        )

    for row in phase.seismogram_parameters:
        sq = row.quality
        if sq is None:
            continue
        frozen = {
            "iccs_cc": sq.iccs_cc if validity.iccs_cc(row.id) else None,
            **{
                k: getattr(sq, k) if mccc_valid else None
                for k in _MCCC_SEISMOGRAM_QUALITY_FIELDS
            },
        }
        if any(v is not None for v in frozen.values()):
            logger.debug(
                f"Adding seismogram quality snapshot for seismogram {row.seismogram_id}."
            )
            seis_quality_snaps.append(
                AimbatSeismogramQualitySnapshot.model_validate(
                    sq,
                    update={
                        **frozen,
                        "id": uuid4(),
                        "seismogram_id": row.seismogram_id,
                        "seismogram_parameters_id": row.id,
                    },
                )
            )

    highest_sequence = session.exec(
        select(func.max(col(AimbatSnapshot.sequence))).where(
            col(AimbatSnapshot.phase_id) == phase.id
        )
    ).one()

    digests = validity.digests(phase.id)
    frozen_members = (
        event_quality_snap.mccc_members if event_quality_snap is not None else None
    )
    aimbat_snapshot = AimbatSnapshot(
        phase=phase,
        sequence=(highest_sequence or 0) + 1,
        phase_parameters_snapshot=phase_parameters_snapshot,
        seismogram_parameters_snapshots=seismogram_parameter_snapshots,
        phase_quality_snapshot=event_quality_snap,
        seismogram_quality_snapshots=seis_quality_snaps,
        comment=comment,
        automatic=automatic,
        mccc_hash=(
            None
            if frozen_members is None
            else digests.mccc([UUID(hex=m) for m in frozen_members])
        ),
        iccs_hash=digests.instance,
    )
    session.add(aimbat_snapshot)
    session.flush()


def create_snapshots_for_added_data(
    session: Session,
    phase_rows: Mapping[UUID, int],
    *,
    comment: str | None = None,
) -> tuple[list[UUID], list[tuple[UUID, str]]]:
    """Snapshot each phase that gained rows in an ingestion call.

    Args:
        session: Database session.
        phase_rows: Number of rows each phase gained, keyed by phase ID.
        comment: Snapshot comment. Defaults to `"Added N pick(s)"` for each
            phase.

    Returns:
        A 2-tuple of `(snapshotted, failures)`: `snapshotted` is the list of
        phase IDs snapshotted; `failures` is a list of `(phase_id, error
        message)` for phases where the snapshot failed. A failure is logged
        here; the caller decides how to surface it.
    """
    snapshotted: list[UUID] = []
    failures: list[tuple[UUID, str]] = []

    for phase_id, count in phase_rows.items():
        if count < 1:
            continue
        phase_comment = comment or f"Added {count} pick{'' if count == 1 else 's'}"
        try:
            # A savepoint per phase, so one failed snapshot discards neither
            # the added data nor the snapshots of other phases.
            with session.begin_nested():
                create_snapshot(
                    session, phase_id, comment=phase_comment, automatic=True
                )
            snapshotted.append(phase_id)
        except Exception as e:
            logger.warning(
                f"Failed to create automatic snapshot for phase {phase_id}: {e}"
            )
            failures.append((phase_id, str(e)))

    return snapshotted, failures


def rollback_to_snapshot(session: Session, snapshot_id: UUID) -> RollbackResult:
    """Rollback to an AIMBAT parameters snapshot.

    Restores the live parameters of the snapshot's phase, and of its rows
    frozen in the snapshot, to the values frozen there. Rows created after
    the snapshot are left as they are. Then restores live quality from the
    snapshot, or another one whose digests match, where possible (see
    `resync_quality`).

    Args:
        session: Database session.
        snapshot_id: Snapshot id.

    Returns:
        The rows left as they are.

    Raises:
        ValueError: If no snapshot with the given ID is found.
    """
    logger.info(f"Rolling back to snapshot with id={snapshot_id}.")

    phase_loads = selectinload(rel(AimbatSnapshot.phase))
    statement = (
        select(AimbatSnapshot)
        .where(AimbatSnapshot.id == snapshot_id)
        .options(
            phase_loads.selectinload(rel(AimbatPhase.parameters)),
            phase_loads.selectinload(rel(AimbatPhase.seismogram_parameters)),
            selectinload(rel(AimbatSnapshot.phase_parameters_snapshot)),
            selectinload(
                rel(AimbatSnapshot.seismogram_parameters_snapshots)
            ).selectinload(rel(AimbatSeismogramParametersSnapshot.parameters)),
        )
    )
    snapshot = session.exec(statement).one_or_none()
    if snapshot is None:
        raise ValueError(f"No AimbatSnapshot found with {snapshot_id=}")

    # create object with just the parameters
    rollback_event_parameters = AimbatPhaseParametersBase.model_validate(
        snapshot.phase_parameters_snapshot
    )
    logger.debug(
        f"Using phase parameters snapshot with id={snapshot.phase_parameters_snapshot.id} for rollback."
    )
    current_event_parameters = snapshot.phase.parameters

    # setting attributes explicitly brings them into the session
    for k in AimbatPhaseParametersBase.model_fields.keys():
        v = getattr(rollback_event_parameters, k)
        logger.debug(f"Setting phase parameter {k} to {v!r} for rollback.")
        setattr(current_event_parameters, k, v)

    session.add(current_event_parameters)

    for seismogram_parameters_snapshot in snapshot.seismogram_parameters_snapshots:
        current_seismogram_parameters = seismogram_parameters_snapshot.parameters
        if current_seismogram_parameters is None:
            # The seismogram was deleted after this snapshot was taken; its
            # frozen row is kept as history but there is nothing live to
            # roll back into.
            continue
        rollback_seismogram_parameters = AimbatSeismogramParametersBase.model_validate(
            seismogram_parameters_snapshot
        )
        logger.debug(
            f"Using seismogram parameters snapshot with id={seismogram_parameters_snapshot.id} for rollback."
        )
        for k in AimbatSeismogramParametersBase.model_fields.keys():
            v = getattr(rollback_seismogram_parameters, k)
            logger.debug(f"Setting seismogram parameter {k} to {v!r} for rollback.")
            setattr(current_seismogram_parameters, k, v)
        session.add(current_seismogram_parameters)

    frozen_rows = {
        s.seismogram_parameters_id for s in snapshot.seismogram_parameters_snapshots
    }
    added_since = tuple(
        row.seismogram_id
        for row in snapshot.phase.seismogram_parameters
        if row.id not in frozen_rows
    )
    if added_since:
        logger.info(
            f"Keeping the parameters of {len(added_since)} seismogram(s) added "
            + "since the snapshot."
        )

    resync_quality(session, snapshot.phase_id, prefer_snapshot_id=snapshot_id)
    return RollbackResult(added_since=added_since)


def _pick_candidate(
    candidates: Sequence[AimbatSnapshot],
    prefer_snapshot_id: UUID | None,
    live_valid: bool,
) -> AimbatSnapshot | None:
    """Choose the snapshot to restore from, if any.

    The preferred snapshot wins when it is a candidate. Otherwise valid live
    values are kept, and invalid ones are restored from the most recent
    candidate.
    """
    preferred = next((c for c in candidates if c.id == prefer_snapshot_id), None)
    if preferred is not None:
        return preferred
    if live_valid or not candidates:
        return None
    return max(candidates, key=lambda s: s.sequence)


def _live_seismogram_quality_map(
    session: Session, snapshot: AimbatSnapshot
) -> dict[UUID, AimbatSeismogramQuality]:
    """Map row ID -> live quality row for the snapshot's frozen rows.

    Keyed on the row each quality snapshot froze rather than its (possibly
    NULL) FK to the live quality row, so a snapshot still resolves to the
    live records after the source quality row has been recreated.
    """
    row_ids = {
        q.seismogram_parameters_id
        for q in snapshot.seismogram_quality_snapshots
        if q.seismogram_parameters_id is not None
    }
    if not row_ids:
        return {}
    return _live_seismogram_quality(session, row_ids)


def _live_seismogram_quality(
    session: Session, row_ids: Collection[UUID]
) -> dict[UUID, AimbatSeismogramQuality]:
    """Map row ID -> live quality row of that row."""
    rows = session.exec(
        select(
            AimbatSeismogramQuality.seismogram_parameters_id, AimbatSeismogramQuality
        ).where(col(AimbatSeismogramQuality.seismogram_parameters_id).in_(row_ids))
    ).all()
    return dict(rows)


def _restore_mccc_quality(
    session: Session, snapshot: AimbatSnapshot, digests: PhaseDigests
) -> None:
    """Copy the frozen MCCC results from `snapshot` into the live records.

    The restored results are stamped with the MCCC digest from `digests`.
    """
    logger.info(f"Restoring MCCC quality from snapshot {snapshot.id}.")

    event_quality_snap = snapshot.phase_quality_snapshot
    assert event_quality_snap is not None  # guaranteed by the candidate filter
    members = event_quality_snap.mccc_members
    assert members is not None  # guaranteed by the candidate filter

    live_event_quality = session.exec(
        select(AimbatPhaseQuality).where(
            col(AimbatPhaseQuality.phase_id) == snapshot.phase_id
        )
    ).one_or_none()
    if live_event_quality is None:
        live_event_quality = AimbatPhaseQuality(phase_id=snapshot.phase_id)
    for k in AimbatPhaseQualityBase.model_fields:
        setattr(live_event_quality, k, getattr(event_quality_snap, k))
    live_event_quality.mccc_fingerprint = digests.mccc(
        [UUID(hex=member) for member in members]
    )
    session.add(live_event_quality)

    frozen = {
        q.seismogram_parameters_id: q
        for q in snapshot.seismogram_quality_snapshots
        if q.seismogram_parameters_id is not None
    }
    live_quality = _live_seismogram_quality(session, list(digests.seismogram_cc))
    # The restored run replaces the live one, so a row that was not in it
    # keeps no MCCC values.
    for row_id, live_seis_quality in live_quality.items():
        seis_quality_snap = frozen.get(row_id)
        for k in _MCCC_SEISMOGRAM_QUALITY_FIELDS:
            value = None if seis_quality_snap is None else getattr(seis_quality_snap, k)
            setattr(live_seis_quality, k, value)
        session.add(live_seis_quality)


def _restore_iccs_cc(
    session: Session,
    snapshot: AimbatSnapshot,
    validity: Validity,
    override_valid: bool,
) -> None:
    """Copy the frozen `iccs_cc` values from `snapshot` into the live records.

    Valid live values are kept, unless `override_valid` is set and the
    snapshot holds a value for that seismogram. Each restored value is stamped
    with its seismogram's current digest.
    """
    logger.info(f"Restoring iccs_cc from snapshot {snapshot.id}.")

    digests = validity.digests(snapshot.phase_id)
    live_quality = _live_seismogram_quality_map(session, snapshot)
    for seis_quality_snap in snapshot.seismogram_quality_snapshots:
        row_id = seis_quality_snap.seismogram_parameters_id
        if row_id is None:
            continue
        live_seis_quality = live_quality.get(row_id)
        if live_seis_quality is None:
            continue
        if validity.iccs_cc(row_id) and (
            not override_valid or seis_quality_snap.iccs_cc is None
        ):
            continue
        live_seis_quality.iccs_cc = seis_quality_snap.iccs_cc
        live_seis_quality.iccs_fingerprint = (
            None
            if seis_quality_snap.iccs_cc is None
            else digests.seismogram_cc.get(row_id)
        )
        session.add(live_seis_quality)


def resync_quality(
    session: Session,
    phase_id: UUID,
    *,
    prefer_snapshot_id: UUID | None = None,
) -> SyncResult:
    """Restore a phase's out-of-date live quality from a matching snapshot.

    Call after changing phase or seismogram parameters, with the change
    staged on `session`. Live values that no longer match the parameters are
    restored from the most recent snapshot whose digests match them, if
    there is one; otherwise they stay, and readers report them as absent.
    Nothing is cleared. `iccs_cc` and the MCCC results are matched
    independently. Flushes; the caller commits.

    Args:
        session: Database session.
        phase_id: ID of the phase whose parameters have just changed.
        prefer_snapshot_id: Snapshot to restore from whenever it matches,
            even over valid live values, for a rollback to that snapshot.

    Returns:
        `SyncResult` recording which metric groups were restored.
    """
    validity = Validity.read(session, phase_id)
    digests = validity.digests(phase_id)
    snapshots = get_snapshots(session, phase_id=phase_id)

    mccc_candidate = _pick_candidate(
        [
            s
            for s in snapshots
            if s.phase_quality_snapshot is not None
            and s.phase_quality_snapshot.mccc_members is not None
            and s.mccc_hash
            == digests.mccc(
                [UUID(hex=m) for m in s.phase_quality_snapshot.mccc_members]
            )
        ],
        prefer_snapshot_id,
        live_valid=validity.mccc(phase_id),
    )
    if mccc_candidate is not None:
        _restore_mccc_quality(session, mccc_candidate, digests)

    iccs_candidate = _pick_candidate(
        [
            s
            for s in snapshots
            if s.iccs_hash == digests.instance
            and any(q.iccs_cc is not None for q in s.seismogram_quality_snapshots)
        ],
        prefer_snapshot_id,
        live_valid=all(validity.iccs_cc(row_id) for row_id in digests.seismogram_cc),
    )
    if iccs_candidate is not None:
        _restore_iccs_cc(
            session,
            iccs_candidate,
            validity,
            override_valid=iccs_candidate.id == prefer_snapshot_id,
        )

    session.flush()
    return SyncResult(
        mccc_synced=mccc_candidate is not None,
        iccs_synced=iccs_candidate is not None,
    )


def delete_snapshot(session: Session, snapshot_id: UUID) -> None:
    """Delete an AIMBAT parameter snapshot.

    Args:
        session: Database session.
        snapshot_id: Snapshot id.

    Raises:
        NoResultFound: If no snapshot with the given ID is found.
    """
    logger.info(f"Deleting snapshot {snapshot_id}.")

    snapshot = session.get(AimbatSnapshot, snapshot_id)
    if snapshot is None:
        raise NoResultFound(f"Unable to find snapshot with {snapshot_id=}")

    session.delete(snapshot)
    flush_deletes(session)


def get_snapshots(
    session: Session,
    event_id: UUID | None = None,
    with_counts: bool = False,
    *,
    phase_id: UUID | None = None,
    phase_name: str | None = None,
) -> Sequence[AimbatSnapshot]:
    """Get the snapshots, optionally filtered by event or phase.

    Args:
        session: Database session.
        event_id: Event ID to filter snapshots by (if none is provided, snapshots for all events are returned).
        with_counts: Whether to load the deferred seismogram counts in the same
            query. Only the table-rendering paths read them; the hash-matching
            paths do not, and pay three scalar subqueries per row if they are.
        phase_id: Phase ID to filter snapshots by.
        phase_name: Phase name to filter snapshots by, across events.

    Returns:
        Snapshots.
    """
    logger.debug("Getting AIMBAT snapshots.")

    statement = select(AimbatSnapshot).join(AimbatPhase)
    if event_id is not None:
        statement = statement.where(col(AimbatPhase.event_id) == event_id)
    if phase_id is not None:
        statement = statement.where(col(AimbatSnapshot.phase_id) == phase_id)
    if phase_name is not None:
        statement = statement.where(col(AimbatPhase.name) == phase_name)

    statement = statement.order_by(
        col(AimbatPhase.event_id), col(AimbatPhase.name), col(AimbatSnapshot.sequence)
    ).options(
        selectinload(rel(AimbatSnapshot.phase)).selectinload(rel(AimbatPhase.event)),
        selectinload(rel(AimbatSnapshot.phase_parameters_snapshot)),
        selectinload(rel(AimbatSnapshot.seismogram_parameters_snapshots)),
        selectinload(rel(AimbatSnapshot.phase_quality_snapshot)),
        selectinload(rel(AimbatSnapshot.seismogram_quality_snapshots)),
        *(undefer_counts(AimbatSnapshot) if with_counts else ()),
    )

    logger.debug(f"Executing statement to get snapshots: {statement}")
    return session.exec(statement).all()


def dump_snapshot_table(
    session: Session,
    event_id: UUID | None = None,
    from_read_model: bool = False,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    phase_name: str | None = None,
) -> list[dict[str, Any]]:
    """Dump snapshot metadata as a list of dicts.

    Args:
        session: Database session.
        event_id: Event ID to filter snapshots by (if none is provided,
            snapshots for all events are dumped).
        from_read_model: Whether to dump from the read model (True) or the ORM model.
            Only affects the `snapshots` table.
        by_alias: Whether to use serialisation aliases for the field names in the output.
        by_title: Whether to use titles for the field names in the output (only
            applicable when from_read_model is True). Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        phase_name: Phase name to filter snapshots by, across events.

    Returns:
        List of dicts representing the snapshots, built from the read model
        when `from_read_model` is True or from the ORM model otherwise.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
        ValueError: If `by_title` is True but `from_read_model` is False.
    """
    logger.debug("Dumping AimbatSnapshot table to json.")

    check_field_name_flags(by_alias, by_title, from_read_model)

    snapshots = get_snapshots(
        session, event_id, with_counts=from_read_model, phase_name=phase_name
    )

    if from_read_model:
        snapshots_read = [
            AimbatSnapshotRead.from_snapshot(s, session=session) for s in snapshots
        ]
        return dump_models(
            snapshots_read,
            AimbatSnapshotRead,
            by_alias=by_alias,
            by_title=by_title,
            exclude=exclude,
        )

    return dump_models(snapshots, AimbatSnapshot, by_alias=by_alias, exclude=exclude)


def get_snapshot_quality(session: Session, snapshot_id: UUID) -> SeismogramQualityStats:
    """Get aggregated quality statistics for a snapshot.

    Args:
        session: Database session.
        snapshot_id: UUID of the snapshot.

    Returns:
        Aggregated seismogram quality statistics from the frozen snapshot records.

    Raises:
        NoResultFound: If no snapshot with the given ID is found.
    """
    logger.debug(f"Getting quality stats for snapshot {snapshot_id}.")

    snapshot = session.exec(
        select(AimbatSnapshot)
        .where(AimbatSnapshot.id == snapshot_id)
        .options(
            selectinload(rel(AimbatSnapshot.seismogram_quality_snapshots)),
            selectinload(rel(AimbatSnapshot.phase_quality_snapshot)),
        )
    ).one_or_none()

    if snapshot is None:
        raise NoResultFound(f"No AimbatSnapshot found with id: {snapshot_id}.")

    return SeismogramQualityStats.from_snapshot(snapshot)


def dump_snapshot_quality_table(
    session: Session,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
    phase_name: str | None = None,
) -> list[dict[str, Any]]:
    """Dump snapshot quality statistics to json.

    Args:
        session: Database session.
        by_alias: Whether to use serialisation aliases for the field names.
        by_title: Whether to use the field title metadata for the field names.
            Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event ID to filter snapshots by (if none is provided, quality
            for all snapshots is dumped).
        phase_name: Phase name to filter snapshots by, across events.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """

    logger.debug("Dumping AIMBAT snapshot quality table to json.")

    check_field_name_flags(by_alias, by_title)

    snapshots = get_snapshots(
        session, event_id, with_counts=True, phase_name=phase_name
    )
    stats = [SeismogramQualityStats.from_snapshot(s) for s in snapshots]

    return dump_models(
        stats,
        SeismogramQualityStats,
        by_alias=by_alias,
        by_title=by_title,
        exclude=(exclude or set()) | {"station_id"},
    )


def _dump_snapshot_related_table(
    session: Session,
    model_name: str,
    model: type[Any],
    extract: Callable[[AimbatSnapshot], Sequence[Any]],
    *,
    event_id: UUID | None = None,
    by_alias: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Dump one kind of record nested under snapshots as a list of dicts.

    Shared by the `dump_*_snapshot_table` functions below, which each supply
    the Pydantic model to serialise with and how to pull its records out of
    one `AimbatSnapshot`. The query is the part they have in common; the
    serialisation is `utils.dump_models`, shared with every other
    `dump_*_table` function.

    Args:
        session: Database session.
        model_name: Name of the model being dumped, for the debug log line.
        model: Pydantic model class of the records being dumped.
        extract: Given one snapshot, returns the records of `model` it holds.
        event_id: Event ID to filter snapshots by (if none is provided,
            snapshots for all events are dumped).
        by_alias: Whether to use serialisation aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.

    Returns:
        List of dicts, one per record returned by `extract`, across all
        matching snapshots.
    """
    logger.debug(f"Dumping {model_name} table to json.")

    snapshots = get_snapshots(session, event_id)
    records = [record for s in snapshots for record in extract(s)]

    return dump_models(records, model, by_alias=by_alias, exclude=exclude)


def dump_phase_parameter_snapshot_table(
    session: Session,
    event_id: UUID | None = None,
    by_alias: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Dump phase parameter snapshots as a list of dicts.

    Args:
        session: Database session.
        event_id: Event ID to filter snapshots by (if none is provided,
            snapshots for all events are dumped).
        by_alias: Whether to use serialisation aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.

    Returns:
        List of dicts, one per phase parameters snapshot.
    """
    return _dump_snapshot_related_table(
        session,
        "AimbatPhaseParametersSnapshot",
        AimbatPhaseParametersSnapshot,
        lambda s: [s.phase_parameters_snapshot],
        event_id=event_id,
        by_alias=by_alias,
        exclude=exclude,
    )


def dump_seismogram_parameter_snapshot_table(
    session: Session,
    event_id: UUID | None = None,
    by_alias: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Dump seismogram parameter snapshots as a list of dicts.

    Args:
        session: Database session.
        event_id: Event ID to filter snapshots by (if none is provided,
            snapshots for all events are dumped).
        by_alias: Whether to use serialisation aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.

    Returns:
        List of dicts, one per seismogram parameters snapshot across all
        matching snapshots.
    """
    return _dump_snapshot_related_table(
        session,
        "AimbatSeismogramParametersSnapshot",
        AimbatSeismogramParametersSnapshot,
        lambda s: s.seismogram_parameters_snapshots,
        event_id=event_id,
        by_alias=by_alias,
        exclude=exclude,
    )


def dump_phase_quality_snapshot_table(
    session: Session,
    event_id: UUID | None = None,
    by_alias: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Dump phase quality snapshots as a list of dicts.

    Args:
        session: Database session.
        event_id: Event ID to filter snapshots by (if none is provided,
            snapshots for all events are dumped).
        by_alias: Whether to use serialisation aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.

    Returns:
        List of dicts, one per snapshot that has a phase quality record
        (snapshots taken before any quality data existed are omitted).
    """
    return _dump_snapshot_related_table(
        session,
        "AimbatPhaseQualitySnapshot",
        AimbatPhaseQualitySnapshot,
        lambda s: (
            [s.phase_quality_snapshot] if s.phase_quality_snapshot is not None else []
        ),
        event_id=event_id,
        by_alias=by_alias,
        exclude=exclude,
    )


def dump_seismogram_quality_snapshot_table(
    session: Session,
    event_id: UUID | None = None,
    by_alias: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Dump seismogram quality snapshots as a list of dicts.

    Args:
        session: Database session.
        event_id: Event ID to filter snapshots by (if none is provided,
            snapshots for all events are dumped).
        by_alias: Whether to use serialisation aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.

    Returns:
        List of dicts, one per seismogram quality record captured across all
        matching snapshots.
    """
    return _dump_snapshot_related_table(
        session,
        "AimbatSeismogramQualitySnapshot",
        AimbatSeismogramQualitySnapshot,
        lambda s: s.seismogram_quality_snapshots,
        event_id=event_id,
        by_alias=by_alias,
        exclude=exclude,
    )


def dump_snapshot_results(
    session: Session,
    snapshot_id: UUID,
    by_alias: bool = False,
) -> dict[str, Any]:
    """Dump per-seismogram MCCC results from a snapshot as a results envelope.

    Returns a dict with event- and snapshot-level header fields plus a
    `seismograms` list containing one entry per seismogram. Event-level
    scalars (`snapshot_id`, `event_id`, `mccc_rmse`) appear once in the
    envelope rather than being repeated on every row.

    Args:
        session: Database session.
        snapshot_id: UUID of the snapshot to export results from.
        by_alias: Whether to use camelCase serialisation aliases for field names.

    Returns:
        Dict with header fields and a `seismograms` list.

    Raises:
        NoResultFound: If no snapshot with the given ID is found.
    """
    logger.debug(f"Dumping per-seismogram results for snapshot {snapshot_id}.")

    snapshot = session.exec(
        select(AimbatSnapshot)
        .where(AimbatSnapshot.id == snapshot_id)
        .options(
            selectinload(rel(AimbatSnapshot.phase)).selectinload(
                rel(AimbatPhase.event)
            ),
            selectinload(rel(AimbatSnapshot.phase_quality_snapshot)),
            selectinload(rel(AimbatSnapshot.seismogram_parameters_snapshots)),
            selectinload(rel(AimbatSnapshot.seismogram_quality_snapshots)),
        )
    ).one_or_none()

    if snapshot is None:
        raise NoResultFound(f"No AimbatSnapshot found with id: {snapshot_id}.")

    eq = snapshot.phase_quality_snapshot
    mccc_rmse = eq.mccc_rmse if eq is not None else None

    # Resolve the frozen seismograms against the live table by their stored id;
    # some may have been deleted since the snapshot was taken.
    frozen_ids = {
        ps.seismogram_id
        for ps in snapshot.seismogram_parameters_snapshots
        if ps.seismogram_id is not None
    }
    live_seismograms: dict[UUID, AimbatSeismogram] = {}
    if frozen_ids:
        live_seismograms = {
            s.id: s
            for s in session.exec(
                select(AimbatSeismogram)
                .where(col(AimbatSeismogram.id).in_(frozen_ids))
                .options(selectinload(rel(AimbatSeismogram.station)))
            ).all()
        }

    quality_map: dict[UUID, AimbatSeismogramQualitySnapshot] = {
        sq.seismogram_id: sq
        for sq in snapshot.seismogram_quality_snapshots
        if sq.seismogram_id is not None
    }

    seismograms = [
        SnapshotSeismogramResult.from_snapshot_records(
            param_snap=ps,
            quality_snap=(
                quality_map.get(ps.seismogram_id)
                if ps.seismogram_id is not None
                else None
            ),
            live_seismogram=(
                live_seismograms.get(ps.seismogram_id)
                if ps.seismogram_id is not None
                else None
            ),
        )
        for ps in snapshot.seismogram_parameters_snapshots
    ]

    event = snapshot.phase.event
    results = SnapshotResults(
        snapshot_id=snapshot.id,
        snapshot_time=snapshot.time,
        snapshot_comment=snapshot.comment,
        phase_id=snapshot.phase_id,
        phase_name=snapshot.phase.name,
        event_id=event.id,
        event_time=event.time,
        event_latitude=event.latitude,
        event_longitude=event.longitude,
        event_depth=event.depth,
        mccc_rmse=mccc_rmse,
        seismograms=seismograms,
    )

    return results.model_dump(mode="json", by_alias=by_alias)
