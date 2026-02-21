from aimbat.logger import logger
from aimbat.utils import uuid_shortener, get_active_event, make_table, TABLE_STYLING
from aimbat.models import (
    AimbatSeismogramParametersBase,
    AimbatSnapshot,
    AimbatEvent,
    AimbatEventParametersBase,
    AimbatEventParameters,
    AimbatEventParametersSnapshot,
    AimbatSeismogramParametersSnapshot,
)
from sqlmodel import Session, select
from rich.console import Console
from collections.abc import Sequence
from typing import overload, Literal, Any
from pydantic import TypeAdapter
import uuid

__all__ = [
    "create_snapshot",
    "rollback_to_snapshot_by_id",
    "rollback_to_snapshot",
    "delete_snapshot_by_id",
    "delete_snapshot",
    "get_snapshots",
    "dump_snapshot_table_to_json",
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

    if all_events:
        logger.debug("Getting snapshots for all events.")
        return session.exec(select(AimbatSnapshot)).all()

    logger.debug("Getting snapshots for active event.")
    select_active_event_snapshots = (
        select(AimbatSnapshot)
        .join(AimbatEventParametersSnapshot)
        .join(AimbatEventParameters)
        .join(AimbatEvent)
        .where(AimbatEvent.active == 1)
    )
    return session.exec(select_active_event_snapshots).all()


@overload
def dump_snapshot_table_to_json(
    session: Session, all_events: bool, as_string: Literal[True]
) -> str: ...


@overload
def dump_snapshot_table_to_json(
    session: Session, all_events: bool, as_string: Literal[False]
) -> list[dict[str, Any]]: ...


def dump_snapshot_table_to_json(
    session: Session, all_events: bool, as_string: bool
) -> str | list[dict[str, Any]]:
    """Dump the `AimbatSnapshot` table data to json."""

    logger.info("Dumping AimbatSeismogramtable to json.")

    adapter: TypeAdapter[Sequence[AimbatSnapshot]] = TypeAdapter(
        Sequence[AimbatSnapshot]
    )

    if all_events:
        parameters = session.exec(select(AimbatSnapshot)).all()
    else:
        parameters = session.exec(
            select(AimbatSnapshot).join(AimbatEvent).where(AimbatEvent.active == 1)
        ).all()

    if as_string:
        return adapter.dump_json(parameters).decode("utf-8")
    return adapter.dump_python(parameters, mode="json")


def print_snapshot_table(session: Session, short: bool, all_events: bool) -> None:
    """Print a pretty table with AIMBAT snapshots.

    Args:
        short: Shorten and format the output to be more human-readable.
        all_events: Print all snapshots instead of limiting to the active event.
    """

    logger.info("Printing AIMBAT snapshots table.")

    title = "AIMBAT snapshots for all events"

    snapshots = get_snapshots(session, all_events)
    logger.debug(f"Found {len(snapshots)} snapshots for the table.")

    if not all_events:
        active_event = get_active_event(session)
        if short:
            title = f"AIMBAT snapshots for event {active_event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_shortener(session, active_event)})"
        else:
            title = (
                f"AIMBAT snapshots for event {active_event.time} (ID={active_event.id})"
            )

    table = make_table(title=title)

    table.add_column(
        "ID (shortened)" if short else "ID",
        justify="center",
        style=TABLE_STYLING.id,
        no_wrap=True,
    )
    table.add_column(
        "Date & Time", justify="center", style=TABLE_STYLING.mine, no_wrap=True
    )
    table.add_column("Comment", justify="center", style=TABLE_STYLING.mine)
    table.add_column("# Seismograms", justify="center", style=TABLE_STYLING.linked)
    if all_events:
        table.add_column("Event ID", justify="center", style=TABLE_STYLING.linked)

    for snapshot in snapshots:
        logger.debug(f"Adding snapshot with id={snapshot.id} to the table.")
        row = [
            (uuid_shortener(session, snapshot) if short else str(snapshot.id)),
            TABLE_STYLING.timestamp_formatter(snapshot.date, short),
            str(snapshot.comment),
            str(len(snapshot.seismogram_parameters_snapshots)),
        ]
        if all_events:
            aimbat_event = snapshot.event
            row.append(
                uuid_shortener(session, aimbat_event) if short else str(aimbat_event.id)
            )
        table.add_row(*row)

    console = Console()
    console.print(table)
