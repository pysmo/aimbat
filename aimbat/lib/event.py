"""Module to manage and view events in AIMBAT."""

from aimbat.lib.common import logger
from aimbat.lib.models import AimbatEvent, AimbatEventParameters
from aimbat.lib.misc.rich_utils import make_table
from rich.console import Console
from sqlmodel import Session, select
from collections.abc import Sequence


def get_active_event(session: Session) -> AimbatEvent:
    """
    Return the currently active event (i.e. the one being processed).

    Parameters:
        session: SQL session.

    Returns:
        Active Event

    Raises:
        RuntimeError: If no active event is found.
    """

    select_active_event = select(AimbatEvent).where(AimbatEvent.active == 1)
    active_event = session.exec(select_active_event).one_or_none()

    logger.debug(f"Active event: {active_event}")

    if active_event is None:
        raise RuntimeError("No active event found.")

    return active_event


def set_active_event_by_id(session: Session, event_id: int) -> None:
    """
    Set the currently selected event (i.e. the one being processed) by its ID.

    Parameters:
        session: SQL session.
        id: ID of AIMBAT Event to set as active one.

    Raises:
        ValueError: If no event with the given ID is found.
    """

    logger.info(f"Setting active event to event with id={event_id}.")

    if event_id not in session.exec(select(AimbatEvent.id)).all():
        raise ValueError(f"No event with id={event_id} found.")

    aimbat_event = session.exec(
        select(AimbatEvent).where(AimbatEvent.id == event_id)
    ).one()
    set_active_event(session, aimbat_event)


def set_active_event(session: Session, event: AimbatEvent) -> None:
    """
    Set the currently selected event (i.e. the one being processed).

    Parameters:
        session: SQL session.
        event: AIMBAT Event to set as active one.
    """

    logger.info(f"Activating {event=}")

    # Because it is possible that no event has been activated yet, we do _not_
    # use get_active_event(), and instead check if there is an active event
    # directly.

    active_event = session.exec(
        select(AimbatEvent).where(AimbatEvent.active == 1)
    ).one_or_none()

    if active_event is None:
        logger.debug(f"No active event yet, activating {event=}.")
    else:
        if active_event.id == event.id:
            logger.debug(f"Event {event} is already active, skipping update.")
            return
        logger.debug(
            f"Updating active event from id={active_event.id} to id={event.id}."
        )
        active_event.active = None
        session.add(active_event)
        session.commit()
    event.active = True
    session.add(event)
    session.commit()


def get_completed_events(session: Session) -> Sequence[AimbatEvent]:
    """Get the events marked as completed.

    Parameters:
        session: SQL session.
    """

    select_completed_events = (
        select(AimbatEvent)
        .join(AimbatEventParameters)
        .where(AimbatEventParameters.completed == 1)
    )

    return session.exec(select_completed_events).all()


def print_event_table(session: Session) -> None:
    """Print a pretty table with AIMBAT events.

    Parameters:
        session: Database session.
    """

    table = make_table(title="AIMBAT Events")
    table.add_column("id", justify="right", style="cyan", no_wrap=True)
    table.add_column("Active", justify="center", style="cyan", no_wrap=True)
    table.add_column("Date & Time", justify="center", style="cyan", no_wrap=True)
    table.add_column("Latitude", justify="center", style="magenta")
    table.add_column("Longitude", justify="center", style="magenta")
    table.add_column("Depth", justify="center", style="magenta")
    table.add_column("Completed", justify="center", style="green")
    table.add_column("# Seismograms", justify="center", style="green")
    table.add_column("# Stations", justify="center", style="green")

    for event in session.exec(select(AimbatEvent)).all():
        active = ""
        if event.active is True:
            active = ":heavy_check_mark:"
        table.add_row(
            str(event.id),
            active,
            str(event.time),
            str(event.latitude),
            str(event.longitude),
            str(event.depth),
            str(event.parameters.completed),
            str(len(event.seismograms)),
            str(len(event.stations)),
        )

    console = Console()
    console.print(table)
