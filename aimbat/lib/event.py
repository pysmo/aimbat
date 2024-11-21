"""Module to manage and view events in AIMBAT."""

from aimbat.lib.common import ic
from aimbat.lib.db import engine
from aimbat.lib.models import AimbatEvent
from aimbat.lib.types import AimbatEventParameterType, AimbatEventParameterName
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select


def event_get_parameter(
    session: Session, event_id: int, parameter_name: AimbatEventParameterName
) -> AimbatEventParameterType:
    """Return the value of an event parameter.

    Parameters:
        session: SQL session.
        event_id: Event ID.
        parameter_name: Parameter name.

    Returns:
        Value of AIMBAT parameter.
    """

    ic()
    ic(session, event_id, parameter_name)

    select_event = select(AimbatEvent).where(AimbatEvent.id == event_id)
    aimbatevent = session.exec(select_event).one()
    return getattr(aimbatevent.parameter, parameter_name)


def event_set_parameter(
    session: Session,
    event_id: int,
    parameter_name: AimbatEventParameterName,
    parameter_value: AimbatEventParameterType,
) -> None:
    """Set the value of an event parameter.

    Parameters:
        session: SQL session.
        event_id: Event ID.
        parameter_name: Parameter name.
        parameter_value: Parameter value.
    """

    ic()
    ic(session, event_id, parameter_name, parameter_value)

    select_event = select(AimbatEvent).where(AimbatEvent.id == event_id)
    aimbatevent = session.exec(select_event).one()
    setattr(aimbatevent.parameter, parameter_name, parameter_value)
    session.add(aimbatevent)
    session.commit()


def event_get_selected_event(session: Session) -> AimbatEvent | None:
    """
    Return the currently selected event (i.e. the one being processed).

    Parameters:
        session: SQL session.

    Returns:
        Selected Event
    """

    ic()
    ic(session)

    select_active_event = select(AimbatEvent).where(AimbatEvent.selected == 1)
    return session.exec(select_active_event).one_or_none()


def event_set_selected_event(session: Session, event: AimbatEvent) -> None:
    """
    Set the currently selected event (i.e. the one being processed).

    Parameters:
        session: SQL session.
        event: AIMBAT Event to set as active one.
    """

    ic()
    ic(session)

    currently_active_event = event_get_selected_event(session)
    if currently_active_event:
        currently_active_event.selected = False
        session.add(currently_active_event)
    event.selected = True
    session.add(event)
    ic(currently_active_event, event)
    session.commit()


def event_print_table() -> None:
    """Print a pretty table with AIMBAT events."""
    ic()

    table = Table(title="AIMBAT Events")
    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Selected", justify="center", style="cyan", no_wrap=True)
    table.add_column("Date & Time", justify="center", style="cyan", no_wrap=True)
    table.add_column("Latitude", justify="center", style="magenta")
    table.add_column("Longitude", justify="center", style="magenta")
    table.add_column("Depth", justify="center", style="magenta")
    table.add_column("Completed", justify="center", style="green")
    table.add_column("# Seismograms", justify="center", style="green")
    table.add_column("# Stations", justify="center", style="green")

    with Session(engine) as session:
        for event in session.exec(select(AimbatEvent)).all():
            assert event.id is not None
            stations = {i.station_id for i in event.seismograms}
            table.add_row(
                str(event.id),
                str(event.selected),
                str(event.time),
                str(event.latitude),
                str(event.longitude),
                str(event.depth),
                str(event.parameter.completed),
                str(len(event.seismograms)),
                str(len(stations)),
            )

    console = Console()
    console.print(table)
