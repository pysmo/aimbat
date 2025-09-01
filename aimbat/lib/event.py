"""Module to manage and view events in AIMBAT."""

from aimbat.lib.common import ic
from aimbat.lib.models import AimbatEvent, AimbatEventParameters, AimbatActiveEvent
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

    select_active_event = select(AimbatEvent).join(AimbatActiveEvent)
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

    aimbat_active_event = session.exec(select(AimbatActiveEvent)).one_or_none()

    if aimbat_active_event is None:
        aimbat_active_event = AimbatActiveEvent(event_id=event.id)
    else:
        aimbat_active_event.event_id = event.id

    session.add(aimbat_active_event)
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
    """Print a pretty table with AIMBAT events.

    Parameters:
        session: Database session.
    """

    ic()
    ic(session)

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

    for event, active_event in session.exec(
        select(AimbatEvent, AimbatActiveEvent).join(AimbatActiveEvent, isouter=True)
    ).all():
        active = ""
        if active_event is not None:
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
