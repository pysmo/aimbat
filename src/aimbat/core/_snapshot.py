import json
import uuid
from collections.abc import Sequence
from typing import Any, Literal, overload

from pydantic import TypeAdapter
from sqlmodel import Session, select

from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatEventParametersSnapshot,
    AimbatSeismogramParametersSnapshot,
    AimbatSnapshot,
    _AimbatSnapshotRead,
)
from aimbat.models._parameters import (
    AimbatEventParametersBase,
    AimbatSeismogramParametersBase,
)

__all__ = [
    "create_snapshot",
    "rollback_to_snapshot_by_id",
    "rollback_to_snapshot",
    "delete_snapshot_by_id",
    "delete_snapshot",
    "get_snapshots",
    "dump_snapshot_tables_to_json",
]


def create_snapshot(
    session: Session, event: AimbatEvent, comment: str | None = None
) -> None:
    """Create a snapshot of the AIMBAT processing parameters.

    Args:
        session: Database session.
        event: AimbatEvent.
        comment: Optional comment.
    """

    logger.info(f"Creating snapshot for event with id={event.id} with {comment=}.")

    event_parameters_snapshot = AimbatEventParametersSnapshot.model_validate(
        event.parameters,
        update={
            "id": uuid.uuid4(),  # we don't want to carry over the id from the input event parameters
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
                "id": uuid.uuid4(),  # we don't want to carry over the id from the input seismogram parameters
                "seismogram_parameters_id": aimbat_seismogram.parameters.id,
            },
        )
        logger.debug(
            f"Adding seismogram parameters snapshot with id={seismogram_parameter_snapshot.id} to snapshot."
        )
        seismogram_parameter_snapshots.append(seismogram_parameter_snapshot)

    aimbat_snapshot = AimbatSnapshot(
        event=event,
        event_parameters_snapshot=event_parameters_snapshot,
        seismogram_parameters_snapshots=seismogram_parameter_snapshots,
        comment=comment,
    )
    session.add(aimbat_snapshot)
    session.commit()


def rollback_to_snapshot_by_id(session: Session, snapshot_id: uuid.UUID) -> None:
    """Rollback to an AIMBAT parameters snapshot.

    Args:
        session: Database session.
        snapshot_id: Snapshot id.
    """

    logger.info(f"Deleting snapshot with id={snapshot_id}.")

    snapshot = session.get(AimbatSnapshot, snapshot_id)

    if snapshot is None:
        raise ValueError(
            f"Unable to delete snapshot: snapshot with id={snapshot_id} not found."
        )

    rollback_to_snapshot(session, snapshot)


def rollback_to_snapshot(session: Session, snapshot: AimbatSnapshot) -> None:
    """Rollback to an AIMBAT parameters snapshot.

    Args:
        snapshot: Snapshot.
    """

    logger.info(f"Rolling back to snapshot with id={snapshot.id}.")

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


def delete_snapshot_by_id(session: Session, snapshot_id: uuid.UUID) -> None:
    """Delete an AIMBAT parameter snapshot.

    Args:
        session: Database session.
        snapshot_id: Snapshot id.
    """

    logger.debug(f"Searching for snapshot with id {snapshot_id}.")

    snapshot = session.get(AimbatSnapshot, snapshot_id)

    if snapshot is None:
        raise ValueError(
            f"Unable to delete snapshot: snapshot with id={snapshot_id} not found."
        )

    delete_snapshot(session, snapshot)


def delete_snapshot(session: Session, snapshot: AimbatSnapshot) -> None:
    """Delete an AIMBAT parameter snapshot.

    Args:
        session: Database session.
        snapshot: Snapshot.
    """

    logger.info(f"Deleting snapshot {snapshot.id}.")

    session.delete(snapshot)
    session.commit()


def get_snapshots(
    session: Session, event: AimbatEvent | None = None, all_events: bool = False
) -> Sequence[AimbatSnapshot]:
    """Get the snapshots for an event.

    Args:
        session: Database session.
        event: Event to return snapshots for.
        all_events: Get the snapshots for all events.

    Returns: Snapshots.
    """

    logger.info("Getting AIMBAT snapshots.")

    if all_events:
        statement = select(AimbatSnapshot)
    else:
        if event is None:
            raise ValueError("An event must be provided when all_events is False.")
        statement = select(AimbatSnapshot).where(AimbatSnapshot.event_id == event.id)

    logger.debug(f"Executing statement to get snapshots: {statement}")
    return session.exec(statement).all()


@overload
def dump_snapshot_tables_to_json(
    session: Session,
    all_events: bool,
    as_string: Literal[True],
    event: AimbatEvent | None = None,
) -> str: ...


@overload
def dump_snapshot_tables_to_json(
    session: Session,
    all_events: bool,
    as_string: Literal[False],
    event: AimbatEvent | None = None,
) -> dict[str, list[dict[str, Any]]]: ...


def dump_snapshot_tables_to_json(
    session: Session,
    all_events: bool,
    as_string: bool,
    event: AimbatEvent | None = None,
) -> str | dict[str, list[dict[str, Any]]]:
    """Dump snapshot data as a dict of lists of dicts.

    Returns a structure with three keys:

    - ``snapshots``: flat list of snapshot metadata.
    - ``event_parameters``: flat list of event parameter snapshots.
    - ``seismogram_parameters``: flat list of seismogram parameter snapshots.

    Each entry includes a ``snapshot_id`` for cross-referencing.

    Args:
        session: Database session.
        all_events: Include snapshots for all events.
        as_string: Return a JSON string when True, otherwise a dict.
        event: Event to dump snapshots for (only used when all_events is False).
    """
    logger.info(f"Dumping AimbatSnapshot tables to json with {all_events=}.")

    snapshots = get_snapshots(session, event=event, all_events=all_events)

    snapshot_adapter: TypeAdapter[Sequence[_AimbatSnapshotRead]] = TypeAdapter(
        Sequence[_AimbatSnapshotRead]
    )
    event_params_adapter: TypeAdapter[Sequence[AimbatEventParametersSnapshot]] = (
        TypeAdapter(Sequence[AimbatEventParametersSnapshot])
    )
    seis_params_adapter: TypeAdapter[Sequence[AimbatSeismogramParametersSnapshot]] = (
        TypeAdapter(Sequence[AimbatSeismogramParametersSnapshot])
    )

    snapshot_reads = [_AimbatSnapshotRead.from_snapshot(s) for s in snapshots]
    event_params = [s.event_parameters_snapshot for s in snapshots]
    seis_params = [sp for s in snapshots for sp in s.seismogram_parameters_snapshots]

    data: dict[str, list[dict[str, Any]]] = {
        "snapshots": snapshot_adapter.dump_python(snapshot_reads, mode="json"),
        "event_parameters": event_params_adapter.dump_python(event_params, mode="json"),
        "seismogram_parameters": seis_params_adapter.dump_python(
            seis_params, mode="json"
        ),
    }

    return json.dumps(data) if as_string else data
