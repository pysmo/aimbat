from __future__ import annotations
from aimbat.lib.common import logger, reverse_uuid_shortener
from aimbat.lib.misc.rich_utils import make_table
from aimbat.lib.models import (
    AimbatSeismogramParametersBase,
    AimbatSnapshot,
    AimbatEvent,
    AimbatEventParametersBase,
    AimbatEventParameters,
    AimbatEventParametersSnapshot,
    AimbatSeismogramParametersSnapshot,
)
from sqlmodel import select
from rich.console import Console
from typing import TYPE_CHECKING
import aimbat.lib.event as event
import uuid

if TYPE_CHECKING:
    from collections.abc import Sequence
    from sqlmodel import Session
    from uuid import UUID


def snapshot_uuid_dict_reversed(
    session: Session, min_length: int = 2
) -> dict[UUID, str]:
    return reverse_uuid_shortener(
        session.exec(select(AimbatSnapshot.id)).all(), min_length
    )


def create_snapshot(session: Session, comment: str | None = None) -> None:
    """Create a snapshot of the AIMBAT processing parameters.

    Parameters:
        session: Database session.
        comment: Optional comment.
    """
    aimbat_event = event.get_active_event(session)

    logger.info(
        f"Creating snapshot for event with id={aimbat_event.id} with {comment=}."
    )

    aimbat_snapshot = AimbatSnapshot(comment=comment)
    session.add(aimbat_snapshot)
    # session.commit()
    logger.debug(
        f"Created snapshot with id={aimbat_snapshot.id}. Now adding parameters..."
    )

    event_parameters_snapshot = AimbatEventParametersSnapshot.model_validate(
        aimbat_event.parameters,
        update={
            "id": uuid.uuid4(),  # we don't want to carry over the id from the active parameters
            "snapshot_id": aimbat_snapshot.id,
            "parameters_id": aimbat_event.parameters.id,
        },
    )
    session.add(event_parameters_snapshot)
    logger.debug(
        f"Added event parameters snapshot with id={event_parameters_snapshot.id} to snapshot."
    )

    for aimbat_seismogram in aimbat_event.seismograms:
        seismogram_parameter_snapshot = AimbatSeismogramParametersSnapshot.model_validate(
            aimbat_seismogram.parameters,
            update={
                "id": uuid.uuid4(),  # we don't want to carry over the id from the active parameters
                "snapshot_id": aimbat_snapshot.id,
                "seismogram_parameters_id": aimbat_seismogram.parameters.id,
            },
        )
        session.add(seismogram_parameter_snapshot)
        logger.debug(
            f"Added seismogram parameters snapshot with id={seismogram_parameter_snapshot.id} to snapshot."
        )

    session.commit()


def rollback_to_snapshot_by_id(session: Session, snapshot_id: UUID) -> None:
    """Rollback to an AIMBAT parameters snapshot.

    Parameters:
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

    Parameters:
        snapshot: Snapshot.
    """

    logger.info(f"Rolling back to snapshot with id={snapshot.id}.")

    current_event_parameters = snapshot.event_parameters_snapshot.parameters
    rollback_event_parameters = AimbatEventParametersBase.model_validate(
        snapshot.event_parameters_snapshot
    )
    logger.debug(
        f"Using event parameters snapshot with id={snapshot.event_parameters_snapshot.id} for rollback."
    )
    for parameter, value in rollback_event_parameters.__dict__.items():
        setattr(current_event_parameters, parameter, value)
    session.add(current_event_parameters)

    for seismogram_parameters_snapshot in snapshot.seismogram_parameters_snapshots:
        current_seismogram_parameters = seismogram_parameters_snapshot.parameters
        rollback_seismogram_parameters = AimbatSeismogramParametersBase.model_validate(
            seismogram_parameters_snapshot
        )
        logger.debug(
            f"Using seismogram parameters snapshot with id={seismogram_parameters_snapshot.id} for rollback."
        )
        for parameter, value in rollback_seismogram_parameters.__dict__.items():
            setattr(current_seismogram_parameters, parameter, value)
        session.add(current_seismogram_parameters)

    session.commit()


def delete_snapshot_by_id(session: Session, snapshot_id: UUID) -> None:
    """Delete an AIMBAT parameter snapshot.

    Parameters:
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

    Parameters:
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

    Parameters:
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


def print_snapshot_table(
    session: Session, format: bool, print_all_events: bool
) -> None:
    """Print a pretty table with AIMBAT snapshots.

    Parameters:
        session: Database session.
        format: Print the output in a more human-readable format.
        print_all_events: Print all snapshots instead of limiting to the active event.
    """

    logger.info("Printing AIMBAT snapshots table.")

    title = "AIMBAT snapshots for all events"
    snapshots = get_snapshots(session, print_all_events)
    logger.debug(f"Found {len(snapshots)} snapshots for the table.")

    event_uuid_dict = reverse_uuid_shortener(
        session.exec(select(AimbatEvent.id)).all(), 2
    )

    if not print_all_events:
        active_event = event.get_active_event(session)
        if format:
            title = f"AIMBAT snapshots for event {active_event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={event.uuid_dict_reversed(session)[active_event.id]})"
        else:
            title = (
                f"AIMBAT snapshots for event {active_event.time} (ID={active_event.id})"
            )

    table = make_table(title=title)

    if format:
        table.add_column("id (shortened)", justify="center", style="cyan", no_wrap=True)
    else:
        table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Date & Time", justify="center", style="cyan", no_wrap=True)
    table.add_column("Comment", justify="center", style="magenta")
    table.add_column("# Seismograms", justify="center", style="green")
    if print_all_events:
        table.add_column("Event ID", justify="center", style="magenta")

    for snapshot in snapshots:
        logger.debug(f"Adding snapshot with id={snapshot.id} to the table.")
        row = [
            (
                snapshot_uuid_dict_reversed(session)[snapshot.id]
                if format
                else str(snapshot.id)
            ),
            (
                snapshot.date.strftime("%Y-%m-%d %H:%M:%S")
                if format
                else str(snapshot.date)
            ),
            str(snapshot.comment),
            str(len(snapshot.seismogram_parameters_snapshots)),
        ]
        if print_all_events:
            event_id = snapshot.event_parameters_snapshot.parameters.event_id
            row.append(event_uuid_dict[event_id] if format else str(event_id))
        table.add_row(*row)

    console = Console()
    console.print(table)
