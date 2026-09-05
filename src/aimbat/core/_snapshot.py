"""Create, restore, and query AIMBAT snapshots of processing parameters and quality metrics.

A snapshot freezes a copy of an event's live event/seismogram parameters and,
when available, its live quality metrics (`AimbatSeismogramQuality.iccs_cc`
and the MCCC diagnostics) for later inspection or rollback.

Snapshots are matched to the live state by two deterministic hashes:
`compute_iccs_hash` covers the parameters (including `select`) that determine
the ICCS stack a seismogram's `iccs_cc` is measured against, and
`compute_mccc_hash` covers the parameters that determine the MCCC inversion.
A live quality record can be repopulated from a matching prior snapshot
instead of being recomputed: `iccs_cc` on an ICCS-hash match, the MCCC
diagnostics on an MCCC-hash match (`sync_from_matching_hash`).
"""

import hashlib
import json
from collections.abc import Callable, Sequence
from typing import Any, NamedTuple
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import func
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from aimbat.logger import logger
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatEventParametersSnapshot,
    AimbatEventQuality,
    AimbatEventQualitySnapshot,
    AimbatSeismogram,
    AimbatSeismogramParametersSnapshot,
    AimbatSeismogramQuality,
    AimbatSeismogramQualitySnapshot,
    AimbatSnapshot,
    AimbatSnapshotRead,
    SeismogramQualityStats,
    SnapshotResults,
    SnapshotSeismogramResult,
)
from aimbat.models._parameters import (
    AimbatEventParametersBase,
    AimbatSeismogramParametersBase,
)
from aimbat.models._quality import (
    AimbatEventQualityBase,
    AimbatSeismogramQualityBase,
)
from aimbat.utils import get_title_map, rel

__all__ = [
    "SyncResult",
    "compute_iccs_hash",
    "compute_mccc_hash",
    "create_snapshot",
    "create_snapshots_for_added_data",
    "delete_snapshot",
    "dump_event_parameter_snapshot_table",
    "dump_event_quality_snapshot_table",
    "dump_seismogram_parameter_snapshot_table",
    "dump_seismogram_quality_snapshot_table",
    "dump_snapshot_quality_table",
    "dump_snapshot_results",
    "dump_snapshot_table",
    "get_snapshot_quality",
    "get_snapshots",
    "rollback_to_snapshot",
    "sync_from_matching_hash",
]


class SyncResult(NamedTuple):
    """Which live quality metrics `sync_from_matching_hash` repopulated."""

    mccc_synced: bool
    iccs_synced: bool


# `completed` is bookkeeping. `min_cc` is the auto-deselection threshold: it
# only ever changes `iccs_cc` indirectly, by changing which seismograms are
# `select`ed on the next run - and `select` is already in the ICCS hash - so a
# bare threshold change should not block reuse of still-valid `iccs_cc` values.
_ICCS_HASH_EVENT_EXCLUDE = {"completed", "min_cc", "mccc_damp", "mccc_min_cc"}
_MCCC_HASH_EVENT_EXCLUDE = {"completed", "min_cc"}

# MCCC membership is recorded by the seismogram quality snapshot rows, so
# changing `select` must not invalidate a prior MCCC result.
_MCCC_HASH_SEISMOGRAM_EXCLUDE = {"select"}

# Every seismogram-level quality field except `iccs_cc` is an MCCC diagnostic.
_MCCC_SEISMOGRAM_QUALITY_FIELDS = tuple(
    k for k in AimbatSeismogramQualityBase.model_fields if k != "iccs_cc"
)


def _compute_parameters_hash(
    event: AimbatEvent,
    *,
    event_exclude: set[str],
    seismogram_exclude: set[str],
) -> str:
    """Hash the event ID plus the selected event and per-seismogram parameters.

    Seismograms are sorted by ID so the digest is independent of load order.
    Including the event ID makes every digest event-scoped.
    """
    event_data = AimbatEventParametersBase.model_validate(event.parameters).model_dump(
        mode="json", exclude=event_exclude
    )
    event_data["event_id"] = str(event.id)
    seis_data = sorted(
        (
            {
                "seismogram_id": str(seis.id),
                **AimbatSeismogramParametersBase.model_validate(
                    seis.parameters
                ).model_dump(mode="json", exclude=seismogram_exclude),
            }
            for seis in event.seismograms
        ),
        key=lambda x: x["seismogram_id"],
    )
    payload = json.dumps(
        {"event": event_data, "seismograms": seis_data}, sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def compute_iccs_hash(event: AimbatEvent) -> str:
    """Compute the hash identifying the ICCS stack these parameters produce.

    Covers the window, taper and bandpass event parameters and the
    per-seismogram `t1`, `flip` and `select` flags. A match means a snapshot's
    `iccs_cc` values were measured against the same stack composition and can
    be restored.

    Args:
        event: AimbatEvent whose current parameters should be hashed.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    logger.debug(f"Computing ICCS parameters hash for event {event.id}.")
    return _compute_parameters_hash(
        event,
        event_exclude=_ICCS_HASH_EVENT_EXCLUDE,
        seismogram_exclude=set(),
    )


def compute_mccc_hash(event: AimbatEvent) -> str:
    """Compute the hash identifying the MCCC inversion these parameters produce.

    Covers the window, taper and bandpass event parameters plus `mccc_damp`
    and `mccc_min_cc`, and the per-seismogram `t1` and `flip` flags. `select`
    is excluded: MCCC run membership is recorded by the snapshot's seismogram
    quality rows, so a selection change does not invalidate a prior result.

    Args:
        event: AimbatEvent whose current parameters should be hashed.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    logger.debug(f"Computing MCCC parameters hash for event {event.id}.")
    return _compute_parameters_hash(
        event,
        event_exclude=_MCCC_HASH_EVENT_EXCLUDE,
        seismogram_exclude=_MCCC_HASH_SEISMOGRAM_EXCLUDE,
    )


def create_snapshot(
    session: Session,
    event: AimbatEvent,
    comment: str | None = None,
    automatic: bool = False,
) -> None:
    """Create a snapshot of the AIMBAT processing parameters and quality metrics.

    Parameter snapshots are always created. Quality snapshots are created
    whenever the corresponding live quality record has at least one non-None
    field. Seismogram quality is omitted when all quality fields are `None`
    (e.g. before any ICCS or MCCC run).

    Args:
        session: Database session.
        event: AimbatEvent.
        comment: Optional comment.
        automatic: Whether this snapshot was created automatically, e.g. by
            `data add`, rather than explicitly by the user.
    """

    logger.info(
        f"Creating snapshot for event {event.id}"
        + (f" with comment '{comment}'" if comment else "")
        + "."
    )

    event = session.exec(
        select(AimbatEvent)
        .where(AimbatEvent.id == event.id)
        .options(
            selectinload(rel(AimbatEvent.parameters)),
            selectinload(rel(AimbatEvent.quality)),
            selectinload(rel(AimbatEvent.seismograms)).options(
                selectinload(rel(AimbatSeismogram.parameters)),
                selectinload(rel(AimbatSeismogram.quality)),
            ),
        )
    ).one()

    event_parameters_snapshot = AimbatEventParametersSnapshot.model_validate(
        event.parameters,
        update={
            "id": uuid4(),  # we don't want to carry over the id from the input event parameters
            "parameters_id": event.parameters.id,
        },
    )
    logger.debug(
        f"Adding event parameters snapshot with id={event_parameters_snapshot.id} to snapshot."
    )

    seismogram_parameter_snapshots = []
    for aimbat_seismogram in event.seismograms:
        seismogram_parameter_snapshot = AimbatSeismogramParametersSnapshot.model_validate(
            aimbat_seismogram.parameters,
            update={
                "id": uuid4(),  # we don't want to carry over the id from the input seismogram parameters
                "seismogram_id": aimbat_seismogram.id,
                "seismogram_parameters_id": aimbat_seismogram.parameters.id,
            },
        )
        logger.debug(
            f"Adding seismogram parameters snapshot with id={seismogram_parameter_snapshot.id} to snapshot."
        )
        seismogram_parameter_snapshots.append(seismogram_parameter_snapshot)

    # Capture quality metrics from the live quality tables.
    event_quality_snap: AimbatEventQualitySnapshot | None = None
    seis_quality_snaps: list[AimbatSeismogramQualitySnapshot] = []

    if event.quality is not None and event.quality.mccc_rmse is not None:
        logger.debug("Capturing event quality snapshot from live quality table.")
        event_quality_snap = AimbatEventQualitySnapshot.model_validate(
            event.quality,
            update={
                "id": uuid4(),
                "event_quality_id": event.quality.id,
            },
        )

    for aimbat_seismogram in event.seismograms:
        sq = aimbat_seismogram.quality
        if sq is None:
            continue
        if any(
            v is not None
            for v in [sq.iccs_cc, sq.mccc_cc_mean, sq.mccc_cc_std, sq.mccc_error]
        ):
            logger.debug(
                f"Adding seismogram quality snapshot for seismogram {aimbat_seismogram.id}."
            )
            seis_quality_snaps.append(
                AimbatSeismogramQualitySnapshot.model_validate(
                    sq,
                    update={
                        "id": uuid4(),
                        "seismogram_id": aimbat_seismogram.id,
                        "seismogram_quality_id": sq.id,
                    },
                )
            )

    highest_sequence = session.exec(
        select(func.max(col(AimbatSnapshot.sequence))).where(
            col(AimbatSnapshot.event_id) == event.id
        )
    ).one()

    aimbat_snapshot = AimbatSnapshot(
        event=event,
        sequence=(highest_sequence or 0) + 1,
        event_parameters_snapshot=event_parameters_snapshot,
        seismogram_parameters_snapshots=seismogram_parameter_snapshots,
        event_quality_snapshot=event_quality_snap,
        seismogram_quality_snapshots=seis_quality_snaps,
        comment=comment,
        automatic=automatic,
        mccc_hash=compute_mccc_hash(event),
        iccs_hash=compute_iccs_hash(event),
    )
    session.add(aimbat_snapshot)
    session.commit()


def create_snapshots_for_added_data(
    session: Session,
    added_datasources: Sequence[AimbatDataSource],
    existing_seismogram_ids: set[UUID],
    *,
    comment: str | None = None,
) -> tuple[list[UUID], list[tuple[UUID, str]]]:
    """Create one snapshot per event that received a newly created seismogram.

    Shared by the CLI's `data add` and the TUI's import action, both of which
    call `add_data_to_project`/`add_seismograms_to_project` first and pass
    its return values straight through.

    Args:
        session: Database session.
        added_datasources: `AimbatDataSource` rows touched by the ingestion
            call, new or reused.
        existing_seismogram_ids: Seismogram IDs that already existed before
            the ingestion call, so only events with a genuinely new
            seismogram are snapshotted.
        comment: Snapshot comment. Defaults to a per-event
            `"Added N seismogram(s)"`.

    Returns:
        A 2-tuple of `(snapshotted, failures)`: `snapshotted` is the list of
        event IDs a snapshot was created for; `failures` is a list of
        `(event_id, error message)` for events whose snapshot failed. A
        failure is logged here; the caller decides how to surface it
        (e.g. `_print_warning` on the CLI, a notification in the TUI).
    """
    from collections import Counter

    new_seismogram_counts: Counter[UUID] = Counter(
        ds.seismogram.event_id
        for ds in added_datasources
        if ds.seismogram_id not in existing_seismogram_ids
    )

    snapshotted: list[UUID] = []
    failures: list[tuple[UUID, str]] = []

    for event_id, count in new_seismogram_counts.items():
        event = session.get(AimbatEvent, event_id)
        if event is None:
            continue
        event_comment = (
            comment or f"Added {count} seismogram{'' if count == 1 else 's'}"
        )
        try:
            create_snapshot(session, event, comment=event_comment, automatic=True)
            snapshotted.append(event_id)
        except Exception as e:
            # By this point the ingestion call has already committed the
            # seismogram data, so a snapshot failure must not be reported as
            # an ingestion failure - that would misleadingly suggest the data
            # itself wasn't added. Roll back and move on to the next event
            # rather than raising, so one event's snapshot failure (e.g. an
            # unexpected quality-data shape) can't suppress the baseline for
            # an unrelated event touched in the same call. A failed commit
            # leaves the session unusable until rolled back, which would
            # otherwise make every subsequent event's snapshot fail too.
            session.rollback()
            logger.warning(
                f"Failed to create automatic snapshot for event {event_id}: {e}"
            )
            failures.append((event_id, str(e)))

    return snapshotted, failures


def rollback_to_snapshot(session: Session, snapshot_id: UUID) -> None:
    """Rollback to an AIMBAT parameters snapshot.

    Restores the event's and its seismograms' live parameters to the values
    frozen in the snapshot, then, in the same session, repopulates live
    quality metrics from a matching snapshot where possible (see
    `sync_from_matching_hash`), preferring the snapshot being rolled back to.
    MCCC quality that cannot be restored is cleared, mirroring the parameter
    setters.

    Args:
        session: Database session.
        snapshot_id: Snapshot id.

    Raises:
        ValueError: If no snapshot with the given ID is found.
    """
    from ._iccs import clear_mccc_quality

    logger.info(f"Rolling back to snapshot with id={snapshot_id}.")

    statement = (
        select(AimbatSnapshot)
        .where(AimbatSnapshot.id == snapshot_id)
        .options(
            selectinload(rel(AimbatSnapshot.event))
            .selectinload(rel(AimbatEvent.seismograms))
            .selectinload(rel(AimbatSeismogram.parameters)),
            selectinload(rel(AimbatSnapshot.event)).selectinload(
                rel(AimbatEvent.parameters)
            ),
            selectinload(rel(AimbatSnapshot.event_parameters_snapshot)),
            selectinload(
                rel(AimbatSnapshot.seismogram_parameters_snapshots)
            ).selectinload(rel(AimbatSeismogramParametersSnapshot.parameters)),
        )
    )
    snapshot = session.exec(statement).one_or_none()
    if snapshot is None:
        raise ValueError(f"No AimbatSnapshot found with {snapshot_id=}")

    # create object with just the parameters
    rollback_event_parameters = AimbatEventParametersBase.model_validate(
        snapshot.event_parameters_snapshot
    )
    logger.debug(
        f"Using event parameters snapshot with id={snapshot.event_parameters_snapshot.id} for rollback."
    )
    current_event_parameters = snapshot.event.parameters

    # setting attributes explicitly brings them into the session
    for k in AimbatEventParametersBase.model_fields.keys():
        v = getattr(rollback_event_parameters, k)
        logger.debug(f"Setting event parameter {k} to {v!r} for rollback.")
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

    event = snapshot.event
    result = sync_from_matching_hash(
        session,
        event.id,
        iccs_hash=compute_iccs_hash(event),
        mccc_hash=compute_mccc_hash(event),
        prefer_snapshot_id=snapshot_id,
    )
    if not result.mccc_synced:
        clear_mccc_quality(session, event)
    session.commit()


def _pick_candidate(
    candidates: Sequence[AimbatSnapshot], prefer_snapshot_id: UUID | None
) -> AimbatSnapshot | None:
    """Choose one snapshot from `candidates`, preferring `prefer_snapshot_id`.

    Falls back to the most recently created candidate.
    """
    if not candidates:
        return None
    preferred = next((c for c in candidates if c.id == prefer_snapshot_id), None)
    if preferred is not None:
        return preferred
    return max(candidates, key=lambda s: s.sequence)


def _live_seismogram_quality_map(
    session: Session, snapshot: AimbatSnapshot
) -> dict[UUID, AimbatSeismogramQuality]:
    """Map `seismogram_id` -> live quality row for the snapshot's frozen seismograms.

    Keyed on the `seismogram_id` stored on each quality snapshot rather than
    its (possibly NULL) FK to the live quality row, so a snapshot still resolves
    to the live records after the source quality row has been recreated. The
    one-quality-row-per-seismogram invariant (`AimbatSeismogram.quality` is a
    scalar relationship) is enforced by a unique index on
    `AimbatSeismogramQuality.seismogram_id`.
    """
    seismogram_ids = {
        q.seismogram_id
        for q in snapshot.seismogram_quality_snapshots
        if q.seismogram_id is not None
    }
    if not seismogram_ids:
        return {}
    rows = session.exec(
        select(AimbatSeismogramQuality).where(
            col(AimbatSeismogramQuality.seismogram_id).in_(seismogram_ids)
        )
    ).all()
    return {row.seismogram_id: row for row in rows}


def _restore_mccc_quality(session: Session, snapshot: AimbatSnapshot) -> None:
    """Copy the frozen MCCC diagnostics from `snapshot` into the live records."""
    logger.info(f"Syncing MCCC quality from snapshot {snapshot.id}.")

    event_quality_snap = snapshot.event_quality_snapshot
    assert event_quality_snap is not None  # guaranteed by the candidate filter

    live_event_quality = session.exec(
        select(AimbatEventQuality).where(
            col(AimbatEventQuality.event_id) == snapshot.event_id
        )
    ).one_or_none()
    if live_event_quality is None:
        logger.warning(
            f"No live event quality record for event {snapshot.event_id}; skipping event quality sync."
        )
    else:
        for k in AimbatEventQualityBase.model_fields:
            setattr(live_event_quality, k, getattr(event_quality_snap, k))
        session.add(live_event_quality)

    live_quality = _live_seismogram_quality_map(session, snapshot)
    for seis_quality_snap in snapshot.seismogram_quality_snapshots:
        if seis_quality_snap.seismogram_id is None:
            continue
        live_seis_quality = live_quality.get(seis_quality_snap.seismogram_id)
        if live_seis_quality is None:
            continue
        for k in _MCCC_SEISMOGRAM_QUALITY_FIELDS:
            setattr(live_seis_quality, k, getattr(seis_quality_snap, k))
        session.add(live_seis_quality)


def _restore_iccs_cc(session: Session, snapshot: AimbatSnapshot) -> None:
    """Copy the frozen `iccs_cc` values from `snapshot` into the live records."""
    logger.info(f"Syncing iccs_cc from snapshot {snapshot.id}.")

    live_quality = _live_seismogram_quality_map(session, snapshot)
    for seis_quality_snap in snapshot.seismogram_quality_snapshots:
        if seis_quality_snap.seismogram_id is None:
            continue
        live_seis_quality = live_quality.get(seis_quality_snap.seismogram_id)
        if live_seis_quality is None:
            continue
        live_seis_quality.iccs_cc = seis_quality_snap.iccs_cc
        session.add(live_seis_quality)


def sync_from_matching_hash(
    session: Session,
    event_id: UUID,
    *,
    iccs_hash: str | None = None,
    mccc_hash: str | None = None,
    prefer_snapshot_id: UUID | None = None,
) -> SyncResult:
    """Repopulate an event's live quality metrics from matching snapshots.

    Considers only this event's snapshots. MCCC diagnostics are restored from
    the most recent snapshot whose `mccc_hash` equals `mccc_hash` and that
    froze MCCC quality; `iccs_cc` is restored from the most recent snapshot
    whose `iccs_hash` equals `iccs_hash` and that froze at least one `iccs_cc`
    value. The two are matched independently, so an ICCS-only snapshot can
    still repopulate `iccs_cc`. `prefer_snapshot_id`, when among the
    candidates, wins the tie-break.

    Pending parameter changes are flushed first so the quality-invalidation
    triggers have fired before the restored values are written. The caller
    owns the transaction and must commit.

    Args:
        session: Database session.
        event_id: Event whose live quality should be synced.
        iccs_hash: Live ICCS hash to match; `None` skips `iccs_cc` restore.
        mccc_hash: Live MCCC hash to match; `None` skips MCCC restore.
        prefer_snapshot_id: Snapshot to prefer when several candidates match.

    Returns:
        `SyncResult` recording which metric groups were repopulated.
    """
    session.flush()

    snapshots = get_snapshots(session, event_id)

    mccc_synced = False
    if mccc_hash is not None:
        mccc_candidate = _pick_candidate(
            [
                s
                for s in snapshots
                if s.mccc_hash == mccc_hash
                and s.event_quality_snapshot is not None
                and s.event_quality_snapshot.mccc_rmse is not None
            ],
            prefer_snapshot_id,
        )
        if mccc_candidate is not None:
            _restore_mccc_quality(session, mccc_candidate)
            mccc_synced = True
        else:
            logger.debug("No snapshot with matching MCCC hash and quality found.")

    iccs_synced = False
    if iccs_hash is not None:
        iccs_candidate = _pick_candidate(
            [
                s
                for s in snapshots
                if s.iccs_hash == iccs_hash
                and any(q.iccs_cc is not None for q in s.seismogram_quality_snapshots)
            ],
            prefer_snapshot_id,
        )
        if iccs_candidate is not None:
            _restore_iccs_cc(session, iccs_candidate)
            iccs_synced = True
        else:
            logger.debug("No snapshot with matching ICCS hash and iccs_cc found.")

    return SyncResult(mccc_synced=mccc_synced, iccs_synced=iccs_synced)


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
    session.commit()


def get_snapshots(
    session: Session, event_id: UUID | None = None
) -> Sequence[AimbatSnapshot]:
    """Get the snapshots, optional filtered by event ID.

    Args:
        session: Database session.
        event_id: Event ID to filter snapshots by (if none is provided, snapshots for all events are returned).

    Returns:
        Snapshots.
    """
    logger.debug("Getting AIMBAT snapshots.")

    if event_id is None:
        statement = select(AimbatSnapshot)
    else:
        statement = select(AimbatSnapshot).where(AimbatSnapshot.event_id == event_id)

    statement = statement.order_by(
        col(AimbatSnapshot.event_id), col(AimbatSnapshot.sequence)
    ).options(
        selectinload(rel(AimbatSnapshot.event)),
        selectinload(rel(AimbatSnapshot.event_parameters_snapshot)),
        selectinload(rel(AimbatSnapshot.seismogram_parameters_snapshots)),
        selectinload(rel(AimbatSnapshot.event_quality_snapshot)),
        selectinload(rel(AimbatSnapshot.seismogram_quality_snapshots)),
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

    Returns:
        List of dicts representing the snapshots, built from the read model
        when `from_read_model` is True or from the ORM model otherwise.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
        ValueError: If `by_title` is True but `from_read_model` is False.
    """
    logger.debug("Dumping AimbatSnapshot table to json.")

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    if not from_read_model and by_title:
        raise ValueError("'by_title' is only supported when 'from_read_model' is True.")

    if exclude is not None:
        exclude: dict[str, set[str]] = {"__all__": exclude}  # type: ignore[no-redef]

    snapshots = get_snapshots(session, event_id)

    if from_read_model:
        snapshot_read_adapter: TypeAdapter[Sequence[AimbatSnapshotRead]] = TypeAdapter(
            Sequence[AimbatSnapshotRead]
        )
        snapshots_read = [
            AimbatSnapshotRead.from_snapshot(s, session=session) for s in snapshots
        ]
        snapshot_dicts = snapshot_read_adapter.dump_python(
            snapshots_read, mode="json", by_alias=by_alias, exclude=exclude
        )

        if by_title:
            title_map = get_title_map(AimbatSnapshotRead)
            snapshot_dicts = [
                {title_map.get(k, k): v for k, v in row.items()}
                for row in snapshot_dicts
            ]
    else:
        snapshot_adapter: TypeAdapter[Sequence[AimbatSnapshot]] = TypeAdapter(
            Sequence[AimbatSnapshot]
        )
        snapshot_dicts = snapshot_adapter.dump_python(
            snapshots, mode="json", by_alias=by_alias, exclude=exclude
        )

    return snapshot_dicts


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
            selectinload(rel(AimbatSnapshot.event_quality_snapshot)),
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

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """

    logger.debug("Dumping AIMBAT snapshot quality table to json.")

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    exclude = (exclude or set()) | {"station_id"}
    exclude: dict[str, set[str]] = {"__all__": exclude}  # type: ignore[no-redef]

    snapshots = get_snapshots(session, event_id)
    stats = [SeismogramQualityStats.from_snapshot(s) for s in snapshots]

    adapter: TypeAdapter[Sequence[SeismogramQualityStats]] = TypeAdapter(
        Sequence[SeismogramQualityStats]
    )
    data = adapter.dump_python(stats, mode="json", exclude=exclude, by_alias=by_alias)

    if by_title:
        title_map = get_title_map(SeismogramQualityStats)
        return [{title_map.get(k, k): v for k, v in row.items()} for row in data]

    return data


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
    one `AimbatSnapshot`.

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

    exclude_spec: dict[str, set[str]] | None = {"__all__": exclude} if exclude else None

    snapshots = get_snapshots(session, event_id)

    adapter: TypeAdapter[Sequence[Any]] = TypeAdapter(Sequence[model])  # type: ignore[valid-type]
    records = [record for s in snapshots for record in extract(s)]
    return adapter.dump_python(
        records, mode="json", by_alias=by_alias, exclude=exclude_spec
    )


def dump_event_parameter_snapshot_table(
    session: Session,
    event_id: UUID | None = None,
    by_alias: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Dump event parameter snapshots as a list of dicts.

    Args:
        session: Database session.
        event_id: Event ID to filter snapshots by (if none is provided,
            snapshots for all events are dumped).
        by_alias: Whether to use serialisation aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.

    Returns:
        List of dicts, one per event parameters snapshot.
    """
    return _dump_snapshot_related_table(
        session,
        "AimbatEventParametersSnapshot",
        AimbatEventParametersSnapshot,
        lambda s: [s.event_parameters_snapshot],
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


def dump_event_quality_snapshot_table(
    session: Session,
    event_id: UUID | None = None,
    by_alias: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Dump event quality snapshots as a list of dicts.

    Args:
        session: Database session.
        event_id: Event ID to filter snapshots by (if none is provided,
            snapshots for all events are dumped).
        by_alias: Whether to use serialisation aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.

    Returns:
        List of dicts, one per snapshot that has an event quality record
        (snapshots taken before any quality data existed are omitted).
    """
    return _dump_snapshot_related_table(
        session,
        "AimbatEventQualitySnapshot",
        AimbatEventQualitySnapshot,
        lambda s: (
            [s.event_quality_snapshot] if s.event_quality_snapshot is not None else []
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
            selectinload(rel(AimbatSnapshot.event)),
            selectinload(rel(AimbatSnapshot.event_quality_snapshot)),
            selectinload(rel(AimbatSnapshot.seismogram_parameters_snapshots)),
            selectinload(rel(AimbatSnapshot.seismogram_quality_snapshots)),
        )
    ).one_or_none()

    if snapshot is None:
        raise NoResultFound(f"No AimbatSnapshot found with id: {snapshot_id}.")

    eq = snapshot.event_quality_snapshot
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

    event = snapshot.event
    results = SnapshotResults(
        snapshot_id=snapshot.id,
        snapshot_time=snapshot.time,
        snapshot_comment=snapshot.comment,
        event_id=snapshot.event_id,
        event_time=event.time,
        event_latitude=event.latitude,
        event_longitude=event.longitude,
        event_depth=event.depth,
        mccc_rmse=mccc_rmse,
        seismograms=seismograms,
    )

    return results.model_dump(mode="json", by_alias=by_alias)
