"""Module to manage and view events in AIMBAT."""

from aimbat.logger import logger
from aimbat.cli.common import HINTS
from aimbat.utils import (
    dump_to_json,
    uuid_shortener,
    get_active_event,
    make_table,
    TABLE_STYLING,
)
from aimbat.models import (
    AimbatEvent,
    AimbatEventParameters,
    AimbatEventParametersBase,
    AimbatStation,
    AimbatSeismogram,
)
from aimbat.aimbat_types import (
    EventParameter,
    EventParameterBool,
    EventParameterFloat,
    EventParameterTimedelta,
)
from rich.console import Console
from sqlmodel import select, Session
from sqlalchemy.exc import NoResultFound
from typing import overload
from pandas import Timedelta
import aimbat.core._station as station

from collections.abc import Sequence
from uuid import UUID

__all__ = [
    "delete_event_by_id",
    "delete_event",
    "get_active_event",
    "set_active_event_by_id",
    "set_active_event",
    "get_completed_events",
    "get_events_using_station",
    "get_event_parameter",
    "set_event_parameter",
    "print_event_table",
    "dump_event_table",
]


def delete_event_by_id(session: Session, event_id: UUID) -> None:
    """Delete an AimbatEvent from the database by ID.

    Args:
        session: Database session.
        event_id: Event ID.

    Raises:
        NoResultFound: If no AimbatEvent is found with the given ID.
    """

    logger.debug(f"Getting event with id={event_id}.")

    event = session.get(AimbatEvent, event_id)
    if event is None:
        raise NoResultFound(
            f"Unable to find event using id: {event_id}. {HINTS.LIST_EVENTS}"
        )
    delete_event(session, event)


def delete_event(session: Session, event: AimbatEvent) -> None:
    """Delete an AimbatEvent from the database.

    Args:
        session: Database session.
        event: Event to delete.
    """

    logger.info(f"Deleting event {event.id}.")

    session.delete(event)
    session.commit()


def set_active_event_by_id(session: Session, event_id: UUID) -> None:
    """
    Set the currently selected event (i.e. the one being processed) by its ID.

    Args:
        session: SQL session.
        event_id: ID of AIMBAT Event to set as active one.

    Raises:
        ValueError: If no event with the given ID is found.
    """
    logger.info(f"Setting active event to event with id={event_id}.")

    if event_id not in session.exec(select(AimbatEvent.id)).all():
        raise ValueError(
            f"No AimbatEvent found with id: {event_id}. {HINTS.LIST_EVENTS}"
        )

    aimbat_event = session.exec(
        select(AimbatEvent).where(AimbatEvent.id == event_id)
    ).one()
    set_active_event(session, aimbat_event)


def set_active_event(session: Session, event: AimbatEvent) -> None:
    """
    Set the active event (i.e. the one being processed).

    Args:
        session: SQL session.
        event: AIMBAT Event to set as active.
    """

    logger.info(f"Activating {event=}")

    event.active = True
    session.add(event)
    session.commit()


def get_completed_events(session: Session) -> Sequence[AimbatEvent]:
    """Get the events marked as completed.

    Args:
        session: SQL session.
    """

    select_completed_events = (
        select(AimbatEvent)
        .join(AimbatEventParameters)
        .where(AimbatEventParameters.completed == 1)
    )

    return session.exec(select_completed_events).all()


def get_events_using_station(
    session: Session, station: AimbatStation
) -> Sequence[AimbatEvent]:
    """Get all events that use a particular station.

    Args:
        session: Database session.
        station: Station to return events for.

    Returns: Events that use the station.
    """

    logger.info(f"Getting events for station: {station.id}.")

    select_events = (
        select(AimbatEvent)
        .join(AimbatSeismogram)
        .join(AimbatStation)
        .where(AimbatStation.id == station.id)
    )

    events = session.exec(select_events).all()

    logger.debug(f"Found {len(events)}.")

    return events


@overload
def get_event_parameter(
    session: Session, name: EventParameterTimedelta
) -> Timedelta: ...


@overload
def get_event_parameter(session: Session, name: EventParameterBool) -> bool: ...


@overload
def get_event_parameter(session: Session, name: EventParameterFloat) -> float: ...


@overload
def get_event_parameter(
    session: Session, name: EventParameter
) -> Timedelta | bool | float: ...


def get_event_parameter(
    session: Session, name: EventParameter
) -> Timedelta | bool | float:
    """Get event parameter value for the active event.

    Args:
        session: Database session.
        name: Name of the parameter.
    """

    active_event = get_active_event(session)

    logger.info(f"Getting {name=} value for {active_event=}.")

    return getattr(active_event.parameters, name)


@overload
def set_event_parameter(
    session: Session, name: EventParameterTimedelta, value: Timedelta
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
    session: Session, name: EventParameter, value: Timedelta | bool | float | str
) -> None: ...


def set_event_parameter(
    session: Session, name: EventParameter, value: Timedelta | bool | float | str
) -> None:
    """Set event parameter value for the active event.

    Args:
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


def print_event_table(session: Session, short: bool = True) -> None:
    """Print a pretty table with AIMBAT events.

    Args:
        short: Shorten and format the output to be more human-readable.
    """

    logger.info("Printing AIMBAT events table.")

    table = make_table(title="AIMBAT Events")
    table.add_column(
        "ID (shortened)" if short else "ID",
        justify="center",
        style=TABLE_STYLING.id,
        no_wrap=True,
    )
    table.add_column("Active", justify="center", style=TABLE_STYLING.mine, no_wrap=True)
    table.add_column(
        "Date & Time", justify="center", style=TABLE_STYLING.mine, no_wrap=True
    )
    table.add_column("Latitude", justify="center", style=TABLE_STYLING.mine)
    table.add_column("Longitude", justify="center", style=TABLE_STYLING.mine)
    table.add_column("Depth", justify="center", style=TABLE_STYLING.mine)
    table.add_column("Completed", justify="center", style=TABLE_STYLING.parameters)
    table.add_column("# Seismograms", justify="center", style=TABLE_STYLING.linked)
    table.add_column("# Stations", justify="center", style=TABLE_STYLING.linked)

    for event in session.exec(select(AimbatEvent)).all():
        logger.debug(f"Adding event with id={event.id} to the table.")
        table.add_row(
            uuid_shortener(session, event) if short else str(event.id),
            TABLE_STYLING.bool_formatter(event.active),
            TABLE_STYLING.timestamp_formatter(event.time, short),
            f"{event.latitude:.3f}" if short else str(event.latitude),
            f"{event.longitude:.3f}" if short else str(event.longitude),
            f"{event.depth:.0f}" if short else str(event.depth),
            TABLE_STYLING.bool_formatter(event.parameters.completed),
            str(len(event.seismograms)),
            str(len(station.get_stations_in_event(session, event))),
        )

    console = Console()
    console.print(table)


def dump_event_table(session: Session) -> None:
    """Dump the table data to json."""

    logger.info("Dumping AIMBAT event table to json.")

    aimbat_events = session.exec(select(AimbatEvent)).all()
    dump_to_json(aimbat_events)
