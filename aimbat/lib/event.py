"""Module to manage and view events in AIMBAT."""

from aimbat.lib.common import ic
from aimbat.lib.models import AimbatEvent, AimbatEventParameters
from aimbat.lib.misc.rich_utils import make_table
from rich.console import Console
from sqlmodel import Session, select
from typing import Sequence


def get_active_event(session: Session) -> AimbatEvent:
    """
    Return the currently active event (i.e. the one being processed).

    Parameters:
        session: SQL session.

    Returns:
        Active Event
    """

    ic()
    ic(session)

    select_active_event = select(AimbatEvent).where(AimbatEvent.is_active == 1)
    active_event = session.exec(select_active_event).one_or_none()
    if active_event is None:
        raise RuntimeError("Active event not found or none selected.")
    return active_event


def set_active_event(session: Session, event: AimbatEvent) -> None:
    """
    Set the currently selected event (i.e. the one being processed).

    Parameters:
        session: SQL session.
        event: AIMBAT Event to set as active one.
    """

    ic()
    ic(session)

    try:
        active_event = get_active_event(session)
        ic(active_event)
        active_event.is_active = False
        session.add(active_event)
    except RuntimeError:
        pass

    event.is_active = True
    session.add(event)
    session.commit()


def get_completed_events(session: Session) -> Sequence[AimbatEvent]:
    """Get the events marked as completed.

    Parameters:
        session: SQL session.
    """

    ic()
    ic(session)

    select_completed_events = (
        select(AimbatEvent)
        .join(AimbatEventParameters)
        .where(AimbatEventParameters.completed == 1)
    )

    return session.exec(select_completed_events).all()


def print_event_table(session: Session) -> None:
    """Print a pretty table with AIMBAT events."""

    ic()
    ic(session)

    table = make_table(title="AIMBAT Events")
    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Active", justify="center", style="cyan", no_wrap=True)
    table.add_column("Date & Time", justify="center", style="cyan", no_wrap=True)
    table.add_column("Latitude", justify="center", style="magenta")
    table.add_column("Longitude", justify="center", style="magenta")
    table.add_column("Depth", justify="center", style="magenta")
    table.add_column("Completed", justify="center", style="green")
    table.add_column("# Seismograms", justify="center", style="green")
    table.add_column("# Stations", justify="center", style="green")

    for event in session.exec(select(AimbatEvent)).all():
        table.add_row(
            str(event.id),
            str(event.is_active),
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
