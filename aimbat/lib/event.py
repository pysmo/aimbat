"""Module to manage and view events in AIMBAT."""

from aimbat.lib.common import logger, reverse_uuid_shortener
from aimbat.lib.misc.rich_utils import make_table
from aimbat.lib.models import (
    AimbatEvent,
    AimbatEventParameters,
    AimbatEventParametersBase,
)
from aimbat.lib.typing import (
    EventParameter,
    EventParameterBool,
    EventParameterFloat,
    EventParameterTimedelta,
)
from rich.console import Console
from sqlmodel import select, Session
from typing import overload
from collections.abc import Sequence
from datetime import timedelta
import uuid


def event_uuid_dict_reversed(
    session: Session, min_length: int = 2
) -> dict[uuid.UUID, str]:
    return reverse_uuid_shortener(
        session.exec(select(AimbatEvent.id)).all(), min_length
    )


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


def set_active_event_by_id(session: Session, event_id: uuid.UUID) -> None:
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
    Set the currently active event (i.e. the one being processed).

    Parameters:
        session: SQL session.
        event: AIMBAT Event to set as active one.
    """

    logger.info(f"Activating {event=}")

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


@overload
def get_event_parameter(
    session: Session, name: EventParameterTimedelta
) -> timedelta: ...


@overload
def get_event_parameter(session: Session, name: EventParameterBool) -> bool: ...


@overload
def get_event_parameter(session: Session, name: EventParameterFloat) -> float: ...


@overload
def get_event_parameter(
    session: Session, name: EventParameter
) -> timedelta | bool | float: ...


def get_event_parameter(
    session: Session, name: EventParameter
) -> timedelta | bool | float:
    """Get event parameter value for the active event.

    Parameters:
        session: Database session.
        name: Name of the parameter.
    """

    active_event = get_active_event(session)

    logger.info(f"Getting {name=} value for {active_event=}.")

    return getattr(active_event.parameters, name)


@overload
def set_event_parameter(
    session: Session, name: EventParameterTimedelta, value: timedelta
) -> None: ...


@overload
def set_event_parameter(
    session: Session, name: EventParameterFloat, value: float
) -> None: ...


@overload
def set_event_parameter(
    session: Session, name: EventParameterBool, value: bool | str
) -> None: ...


@overload
def set_event_parameter(
    session: Session, name: EventParameter, value: timedelta | bool | float | str
) -> None: ...


def set_event_parameter(
    session: Session, name: EventParameter, value: timedelta | bool | float | str
) -> None:
    """Set event parameter value for the active event.

    Parameters:
        session: Database session.
        name: Name of the parameter.
        value: Value to set.
    """

    active_event = get_active_event(session)

    logger.info(f"Setting {name=} to {value} for {active_event=}.")

    parameters = AimbatEventParametersBase.model_validate(
        active_event.parameters, update={name: value}
    )
    setattr(active_event.parameters, name, getattr(parameters, name))
    session.add(active_event)
    session.commit()


def print_event_table(session: Session, format: bool = True) -> None:
    """Print a pretty table with AIMBAT events.

    Parameters:
        session: Database session.
        format: Format the output to be more human-readable.
    """

    logger.info("Printing AIMBAT events table.")

    table = make_table(title="AIMBAT Events")
    if format:
        table.add_column("id (shortened)", justify="center", style="cyan", no_wrap=True)
    else:
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
        logger.debug(f"Adding event with id={event.id} to the table.")
        table.add_row(
            event_uuid_dict_reversed(session)[event.id] if format else str(event.id),
            ":heavy_check_mark:" if event.active is True else "",
            event.time.strftime("%Y-%m-%d %H:%M:%S") if format else str(event.time),
            f"{event.latitude:.3f}" if format else str(event.latitude),
            f"{event.longitude:.3f}" if format else str(event.longitude),
            f"{event.depth:.0f}" if format else str(event.depth),
            str(event.parameters.completed),
            str(len(event.seismograms)),
            str(len(event.stations)),
        )

    console = Console()
    console.print(table)
