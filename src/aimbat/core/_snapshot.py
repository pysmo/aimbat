import hashlib
import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatEventParametersSnapshot,
    AimbatEventQuality,
    AimbatEventQualitySnapshot,
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
    "compute_parameters_hash",
    "create_snapshot",
    "rollback_to_snapshot",
    "sync_from_matching_hash",
    "delete_snapshot",
    "get_snapshots",
    "get_snapshot_quality",
    "dump_snapshot_table",
    "dump_snapshot_quality_table",
    "dump_snapshot_results",
    "dump_event_parameter_snapshot_table",
    "dump_seismogram_parameter_snapshot_table",
    "dump_event_quality_snapshot_table",
    "dump_seismogram_quality_snapshot_table",
]


def compute_parameters_hash(event: AimbatEvent) -> str:
    """Compute a deterministic SHA-256 hash of the event's current parameters.

    Hashes the event ID, all event-level parameters, and per-seismogram
    parameters. Seismograms are sorted by ID so the result is independent of
    load order. Including the event ID means hashes are inherently
    event-scoped and will never collide across events.

    Excluded fields:

    - `completed` (event): does not affect seismogram processing.
    - `select` (seismogram): determines which seismograms are passed to MCCC
      but does not affect the computation for any individual seismogram.
      Membership of the actual MCCC run is captured by the seismogram quality
      records in the snapshot, so changing selection state should not
      invalidate a prior MCCC result.

    Args:
        event: AimbatEvent whose current parameters should be hashed.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    logger.debug(f"Computing parameters hash for event {event.id}.")

    # exclude completed field since it does not affect the seismograms directly.
    event_data = AimbatEventParametersBase.model_validate(event.parameters).model_dump(
        mode="json", exclude={"completed"}
    )
    event_data["event_id"] = str(event.id)
    seis_data = sorted(
        [
            {
                "seismogram_id": str(seis.id),
                **AimbatSeismogramParametersBase.model_validate(
                    seis.parameters
                ).model_dump(mode="json", exclude={"select"}),
            }
            for seis in event.seismograms
        ],
        key=lambda x: x["seismogram_id"],
    )
    payload = json.dumps(
        {"event": event_data, "seismograms": seis_data}, sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def create_snapshot(
    session: Session,
    event: AimbatEvent,
    comment: str | None = None,
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
                        "seismogram_quality_id": sq.id,
                    },
                )
            )

    aimbat_snapshot = AimbatSnapshot(
        event=event,
        event_parameters_snapshot=event_parameters_snapshot,
        seismogram_parameters_snapshots=seismogram_parameter_snapshots,
        event_quality_snapshot=event_quality_snap,
        seismogram_quality_snapshots=seis_quality_snaps,
        comment=comment,
        parameters_hash=compute_parameters_hash(event),
    )
    session.add(aimbat_snapshot)
    session.commit()


def rollback_to_snapshot(session: Session, snapshot_id: UUID) -> None:
    """Rollback to an AIMBAT parameters snapshot.

    Args:
        snapshot_id: Snapshot id.
    """

    logger.info(f"Rolling back to snapshot with id={snapshot_id}.")

    statement = (
        select(AimbatSnapshot)
        .where(AimbatSnapshot.id == snapshot_id)
        .options(
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
        rollback_seismogram_parameters = AimbatSeismogramParametersBase.model_validate(
            seismogram_parameters_snapshot
        )
        logger.debug(
            f"Using seismogram parameters snapshot with id={seismogram_parameters_snapshot.id} for rollback."
        )
        current_seismogram_parameters = seismogram_parameters_snapshot.parameters
        for k in AimbatSeismogramParametersBase.model_fields.keys():
            v = getattr(rollback_seismogram_parameters, k)
            logger.debug(f"Setting seismogram parameter {k} to {v!r} for rollback.")
            setattr(current_seismogram_parameters, k, v)
        session.add(current_seismogram_parameters)

    session.commit()
    sync_from_matching_hash(session, snapshot_id=snapshot_id)


def sync_from_matching_hash(
    session: Session,
    parameters_hash: str | None = None,
    snapshot_id: UUID | None = None,
) -> bool:
    """Sync live quality metrics from a snapshot whose parameter hash matches the given hash.

    Searches all snapshots for candidates whose `parameters_hash` matches and
    that have MCCC quality data. When multiple candidates exist, `snapshot_id`
    is used as a tie-breaker (preferred if it is among them); otherwise the
    most recent candidate is used.

    Args:
        session: Database session.
        parameters_hash: Hash to match against snapshot hashes. If None and
            `snapshot_id` is provided, the hash is derived from that snapshot.
        snapshot_id: Optional tie-breaker when multiple candidates share the
            same hash.

    Returns:
        True if quality metrics were synced, False if no suitable candidate
        was found.

    Raises:
        ValueError: If both are provided but the hashes differ.
    """
    if parameters_hash is None:
        if snapshot_id is None:
            return False
        snapshot = session.get(AimbatSnapshot, snapshot_id)
        if snapshot is None:
            raise ValueError(f"No AimbatSnapshot found with {snapshot_id=}")
        parameters_hash = snapshot.parameters_hash
        if parameters_hash is None:
            return False
    elif snapshot_id is not None:
        snapshot = session.get(AimbatSnapshot, snapshot_id)
        if snapshot is not None and snapshot.parameters_hash != parameters_hash:
            raise ValueError(
                f"Provided parameters_hash does not match hash on snapshot {snapshot_id}."
            )

    logger.debug(f"Looking for quality metrics to sync for hash {parameters_hash}.")

    candidates = [
        s
        for s in get_snapshots(session)
        if s.parameters_hash == parameters_hash
        and s.event_quality_snapshot is not None
        and s.event_quality_snapshot.mccc_rmse is not None
    ]
    if not candidates:
        logger.debug("No snapshot with matching hash and MCCC quality data found.")
        return False

    preferred = next((c for c in candidates if c.id == snapshot_id), None)
    snapshot = (
        preferred if preferred is not None else max(candidates, key=lambda s: s.time)
    )

    logger.info(f"Syncing quality metrics from snapshot {snapshot.id}.")

    event_quality_snap = snapshot.event_quality_snapshot
    if event_quality_snap is None:
        raise ValueError(
            f"Snapshot {snapshot.id} has no event quality data despite passing filter."
        )
    live_event_quality = session.get(
        AimbatEventQuality, event_quality_snap.event_quality_id
    )
    if live_event_quality is None:
        logger.warning(
            f"Live event quality record {event_quality_snap.event_quality_id} not found; skipping event quality sync."
        )
    else:
        for k in AimbatEventQualityBase.model_fields:
            v = getattr(event_quality_snap, k)
            logger.debug(f"Setting event quality {k} to {v!r} from snapshot.")
            setattr(live_event_quality, k, v)
        session.add(live_event_quality)

    for seis_quality_snap in snapshot.seismogram_quality_snapshots:
        live_seis_quality = session.get(
            AimbatSeismogramQuality, seis_quality_snap.seismogram_quality_id
        )
        if live_seis_quality is None:
            logger.warning(
                f"Live seismogram quality record {seis_quality_snap.seismogram_quality_id} not found; skipping."
            )
            continue
        for k in AimbatSeismogramQualityBase.model_fields:
            v = getattr(seis_quality_snap, k)
            logger.debug(f"Setting seismogram quality {k} to {v!r} from snapshot.")
            setattr(live_seis_quality, k, v)
        session.add(live_seis_quality)

    session.commit()
    return True


def delete_snapshot(session: Session, snapshot_id: UUID) -> None:
    """Delete an AIMBAT parameter snapshot.

    Args:
        snapshot_id: Snapshot id.
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

    Returns: Snapshots.
    """
    logger.debug("Getting AIMBAT snapshots.")

    if event_id is None:
        statement = select(AimbatSnapshot)
    else:
        statement = select(AimbatSnapshot).where(AimbatSnapshot.event_id == event_id)

    statement = statement.options(
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
        by_alias: Whether to use serialization aliases for the field names in the output.
        by_title: Whether to use titles for the field names in the output (only
            applicable when from_read_model is True). Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
    """
    logger.debug("Dumping AimbatSnapshot table to json.")

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    if not from_read_model and by_title:
        raise ValueError("'by_title' is only supported when 'from_read_model' is True.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

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
        by_alias: Whether to use serialization aliases for the field names.
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
    exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

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
        by_alias: Whether to use serialization aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.
    """
    logger.debug("Dumping AimbatEventParametersSnapshot table to json.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    snapshots = get_snapshots(session, event_id)

    event_params_adapter: TypeAdapter[Sequence[AimbatEventParametersSnapshot]] = (
        TypeAdapter(Sequence[AimbatEventParametersSnapshot])
    )
    event_snaps = [s.event_parameters_snapshot for s in snapshots]
    event_dicts = event_params_adapter.dump_python(
        event_snaps, mode="json", by_alias=by_alias, exclude=exclude
    )

    return event_dicts


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
        by_alias: Whether to use serialization aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.
    """
    logger.debug("Dumping AimbatSeismogramParametersSnapshot table to json.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    snapshots = get_snapshots(session, event_id)

    seis_params_adapter: TypeAdapter[Sequence[AimbatSeismogramParametersSnapshot]] = (
        TypeAdapter(Sequence[AimbatSeismogramParametersSnapshot])
    )
    seis_snaps = [sp for s in snapshots for sp in s.seismogram_parameters_snapshots]
    seis_dicts = seis_params_adapter.dump_python(
        seis_snaps, mode="json", by_alias=by_alias, exclude=exclude
    )

    return seis_dicts


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
        by_alias: Whether to use serialization aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.
    """
    logger.debug("Dumping AimbatEventQualitySnapshot table to json.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    snapshots = get_snapshots(session, event_id)

    event_quality_adapter: TypeAdapter[Sequence[AimbatEventQualitySnapshot]] = (
        TypeAdapter(Sequence[AimbatEventQualitySnapshot])
    )
    # Filter out snapshots that don't have event quality records.
    event_quality_snaps = [
        s.event_quality_snapshot
        for s in snapshots
        if s.event_quality_snapshot is not None
    ]
    event_quality_dicts = event_quality_adapter.dump_python(
        event_quality_snaps, mode="json", by_alias=by_alias, exclude=exclude
    )

    return event_quality_dicts


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
        by_alias: Whether to use serialization aliases for the field names in the output.
        exclude: Set of field names to exclude from the output.
    """
    logger.debug("Dumping AimbatSeismogramQualitySnapshot table to json.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    snapshots = get_snapshots(session, event_id)

    seis_quality_adapter: TypeAdapter[Sequence[AimbatSeismogramQualitySnapshot]] = (
        TypeAdapter(Sequence[AimbatSeismogramQualitySnapshot])
    )
    # Collect all seismogram quality records from all snapshots.
    seis_quality_snaps = [
        sq for s in snapshots for sq in s.seismogram_quality_snapshots
    ]
    seis_quality_dicts = seis_quality_adapter.dump_python(
        seis_quality_snaps, mode="json", by_alias=by_alias, exclude=exclude
    )

    return seis_quality_dicts


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
            selectinload(rel(AimbatSnapshot.seismogram_parameters_snapshots)).options(
                selectinload(
                    rel(AimbatSeismogramParametersSnapshot.parameters)
                ).options(
                    selectinload(
                        rel(AimbatSeismogramParameters.seismogram)
                    ).selectinload(rel(AimbatSeismogram.station))
                )
            ),
            selectinload(rel(AimbatSnapshot.seismogram_quality_snapshots)).selectinload(
                rel(AimbatSeismogramQualitySnapshot.quality)
            ),
        )
    ).one_or_none()

    if snapshot is None:
        raise NoResultFound(f"No AimbatSnapshot found with id: {snapshot_id}.")

    eq = snapshot.event_quality_snapshot
    mccc_rmse = eq.mccc_rmse if eq is not None else None

    # Build a lookup from seismogram_id → quality snapshot.
    quality_map: dict[UUID, AimbatSeismogramQualitySnapshot] = {
        sq.quality.seismogram_id: sq for sq in snapshot.seismogram_quality_snapshots
    }

    seismograms = [
        SnapshotSeismogramResult.from_snapshot_records(
            param_snap=ps,
            quality_snap=quality_map.get(ps.parameters.seismogram_id),
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
        event_depth_km=event.depth / 1000 if event.depth is not None else None,
        mccc_rmse=mccc_rmse,
        seismograms=seismograms,
    )

    return results.model_dump(mode="json", by_alias=by_alias)
