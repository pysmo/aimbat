import uuid
import json
from aimbat.core import get_active_event
from aimbat.logger import logger
from aimbat.utils import uuid_shortener, json_to_table, TABLE_STYLING
from aimbat.models import (
    AimbatSeismogramParametersBase,
    AimbatSnapshot,
    AimbatSnapshotRead,
    AimbatEvent,
    AimbatEventParametersBase,
    AimbatEventParametersSnapshot,
    AimbatSeismogramParametersSnapshot,
)
from sqlmodel import Session, select
from sqlalchemy import true
from pandas import Timestamp
from collections.abc import Sequence
from typing import overload, Literal, Any
from pydantic import TypeAdapter

__all__ = [
    "create_snapshot",
    "rollback_to_snapshot_by_id",
    "rollback_to_snapshot",
    "delete_snapshot_by_id",
    "delete_snapshot",
    "get_snapshots",
    "dump_snapshot_tables_to_json",
    "print_snapshot_table",
]


def create_snapshot(session: Session, comment: str | None = None) -> None:
    """Create a snapshot of the AIMBAT processing parameters.

    Args:
        session: Database session.
        comment: Optional comment.
    """
    active_aimbat_event = get_active_event(session)

    logger.info(
        f"Creating snapshot for event with id={active_aimbat_event.id} with {comment=}."
    )

    event_parameters_snapshot = AimbatEventParametersSnapshot.model_validate(
        active_aimbat_event.parameters,
        update={
            "id": uuid.uuid4(),  # we don't want to carry over the id from the active parameters
            "parameters_id": active_aimbat_event.parameters.id,
        },
    )
    logger.debug(
        f"Adding event parameters snapshot with id={event_parameters_snapshot.id} to snapshot."
    )

    seismogram_parameter_snapshots = []
    for aimbat_seismogram in active_aimbat_event.seismograms:
        seismogram_parameter_snapshot = AimbatSeismogramParametersSnapshot.model_validate(
            aimbat_seismogram.parameters,
            update={
                "id": uuid.uuid4(),  # we don't want to carry over the id from the active parameters
                "seismogram_parameters_id": aimbat_seismogram.parameters.id,
            },
        )
        logger.debug(
            f"Adding seismogram parameters snapshot with id={seismogram_parameter_snapshot.id} to snapshot."
        )
        seismogram_parameter_snapshots.append(seismogram_parameter_snapshot)

    aimbat_snapshot = AimbatSnapshot(
        event=active_aimbat_event,
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
    for k, v in rollback_event_parameters.model_dump().items():
        setattr(current_event_parameters, k, v)

    session.add(current_event_parameters)

    for seismogram_parameters_snapshot in snapshot.seismogram_parameters_snapshots:
        # create object with just the parameters
        rollback_seismogram_parameters = AimbatSeismogramParametersBase.model_validate(
            seismogram_parameters_snapshot
        )
        logger.debug(
            f"Using seismogram parameters snapshot with id={seismogram_parameters_snapshot.id} for rollback."
        )
        # setting attributes explicitly brings them into the session
        current_seismogram_parameters = seismogram_parameters_snapshot.parameters
        for parameter, value in rollback_seismogram_parameters.model_dump().items():
            setattr(current_seismogram_parameters, parameter, value)
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
    session: Session, all_events: bool = False
) -> Sequence[AimbatSnapshot]:
    """Get the snapshots for the active avent.

    Args:
        session: Database session.
        all_events: Get the selected snapshots for all events.

    Returns: Snapshots.
    """

    logger.info("Getting AIMBAT snapshots.")

    statement = (
        select(AimbatSnapshot)
        .join(AimbatEvent)
        .where(AimbatEvent.active == True if not all_events else true())  # noqa: E712
    )

    logger.debug(f"Executing statement to get snapshots: {statement}")
    return session.exec(statement).all()


@overload
def dump_snapshot_tables_to_json(
    session: Session, all_events: bool, as_string: Literal[True]
) -> str: ...


@overload
def dump_snapshot_tables_to_json(
    session: Session, all_events: bool, as_string: Literal[False]
) -> dict[str, list[dict[str, Any]]]: ...


def dump_snapshot_tables_to_json(
    session: Session, all_events: bool, as_string: bool
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
    """
    logger.info(f"Dumping AimbatSnapshot tables to json with {all_events=}.")

    snapshots = get_snapshots(session, all_events)

    snapshot_adapter: TypeAdapter[Sequence[AimbatSnapshotRead]] = TypeAdapter(
        Sequence[AimbatSnapshotRead]
    )
    event_params_adapter: TypeAdapter[Sequence[AimbatEventParametersSnapshot]] = (
        TypeAdapter(Sequence[AimbatEventParametersSnapshot])
    )
    seis_params_adapter: TypeAdapter[Sequence[AimbatSeismogramParametersSnapshot]] = (
        TypeAdapter(Sequence[AimbatSeismogramParametersSnapshot])
    )

    snapshot_reads = [AimbatSnapshotRead.from_snapshot(s) for s in snapshots]
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


def print_snapshot_table(session: Session, short: bool, all_events: bool) -> None:
    """Print a pretty table with AIMBAT snapshots.

    Uses the ``snapshots`` portion of :func:`dump_snapshot_tables_to_json`
    and renders it via :func:`~aimbat.utils.json_to_table`.

    Args:
        session: Database session.
        short: Shorten and format the output to be more human-readable.
        all_events: Print all snapshots instead of limiting to the active event.
    """

    logger.info("Printing AIMBAT snapshots table.")

    title = "AIMBAT snapshots for all events"

    if not all_events:
        active_event = get_active_event(session)
        if short:
            title = f"AIMBAT snapshots for event {active_event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_shortener(session, active_event)})"
        else:
            title = (
                f"AIMBAT snapshots for event {active_event.time} (ID={active_event.id})"
            )

    data = dump_snapshot_tables_to_json(session, all_events, as_string=False)
    snapshot_data = data["snapshots"]

    column_order = ["id", "date", "comment", "seismogram_count"]
    if all_events:
        column_order.append("event_id")

    skip_keys = [] if all_events else ["event_id"]

    json_to_table(
        data=snapshot_data,
        title=title,
        column_order=column_order,
        skip_keys=skip_keys,
        formatters={
            "id": lambda x: (
                uuid_shortener(session, AimbatSnapshot, str_uuid=x) if short else x
            ),
            "date": lambda x: TABLE_STYLING.timestamp_formatter(Timestamp(x), short),
            "event_id": lambda x: (
                uuid_shortener(session, AimbatEvent, str_uuid=x) if short else x
            ),
        },
        common_column_kwargs={"justify": "center"},
        column_kwargs={
            "id": {
                "header": "ID (shortened)" if short else "ID",
                "style": TABLE_STYLING.id,
                "no_wrap": True,
            },
            "date": {
                "header": "Date & Time",
                "style": TABLE_STYLING.mine,
                "no_wrap": True,
            },
            "comment": {"style": TABLE_STYLING.mine},
            "seismogram_count": {
                "header": "# Seismograms",
                "style": TABLE_STYLING.linked,
            },
            "event_id": {
                "header": "Event ID (shortened)" if short else "Event ID",
                "style": TABLE_STYLING.linked,
            },
        },
    )
