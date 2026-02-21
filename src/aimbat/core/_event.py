"""Module to manage and view events in AIMBAT."""

from aimbat.logger import logger
from aimbat.cli._common import HINTS
from aimbat.utils import (
    uuid_shortener,
    get_active_event,
    make_table,
    json_to_table,
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
from pydantic import TypeAdapter
from rich.console import Console
from sqlmodel import select, Session
from sqlalchemy.exc import NoResultFound
from typing import overload, Any, Literal
from pandas import Timedelta
from collections.abc import Sequence
from uuid import UUID
import aimbat.core._station as station

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
    "dump_event_table_to_json",
    "print_event_table",
    "dump_event_parameter_table_to_json",
    "print_event_parameter_table",
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


def dump_event_table_to_json(session: Session) -> str:
    """Dump the table data to json."""

    logger.info("Dumping AIMBAT event table to json.")
    adapter: TypeAdapter[Sequence[AimbatEvent]] = TypeAdapter(Sequence[AimbatEvent])
    aimbat_event = session.exec(select(AimbatEvent)).all()

    return adapter.dump_json(aimbat_event).decode("utf-8")


def print_event_table(session: Session, short: bool) -> None:
    """Print a pretty table with AIMBAT events.

    Args:
        session: Database session.
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


@overload
def dump_event_parameter_table_to_json(
    session: Session, all_events: bool, as_string: Literal[True]
) -> str: ...


@overload
def dump_event_parameter_table_to_json(
    session: Session, all_events: Literal[False], as_string: Literal[False]
) -> dict[str, Any]: ...


@overload
def dump_event_parameter_table_to_json(
    session: Session, all_events: Literal[True], as_string: Literal[False]
) -> list[dict[str, Any]]: ...


def dump_event_parameter_table_to_json(
    session: Session, all_events: bool, as_string: bool
) -> str | dict[str, Any] | list[dict[str, Any]]:
    """Dump the event parameter table data to json."""

    logger.info("Dumping AIMBAT event parameter table to json.")

    if all_events:
        adapter: TypeAdapter[Sequence[AimbatEventParameters]] = TypeAdapter(
            Sequence[AimbatEventParameters]
        )
        parameters = session.exec(select(AimbatEventParameters)).all()
        if as_string:
            return adapter.dump_json(parameters).decode("utf-8")
        else:
            return adapter.dump_python(parameters, mode="json")

    active_event = get_active_event(session)

    if as_string:
        return active_event.parameters.model_dump_json()
    return active_event.parameters.model_dump(mode="json")


def print_event_parameter_table(
    session: Session, short: bool, all_events: bool
) -> None:
    """Print a pretty table with AIMBAT parameter values for the active event.

    Args:
        short: Shorten and format the output to be more human-readable.
        all_events: Whether to print parameters for all events or just the active one.
    """

    if all_events:
        logger.info("Printing AIMBAT event parameters table for all events.")
        json_to_table(
            data=dump_event_parameter_table_to_json(
                session, all_events=True, as_string=False
            ),
            title="Event parameters for all events",
            skip_keys=["id"],
            column_order=[
                "event_id",
                "completed",
                "window_pre",
                "window_post",
                "min_ccnorm",
            ],
            formatters={
                "event_id": lambda x: (
                    uuid_shortener(session, AimbatEvent, str_uuid=x) if short else x
                ),
            },
            common_column_kwargs={"highlight": True},
            column_kwargs={
                "event_id": {
                    "header": "Event ID (shortened)" if short else "Event ID",
                    "justify": "center",
                    "style": TABLE_STYLING.mine,
                },
            },
        )
    else:
        logger.info("Printing AIMBAT event parameters table for active event.")

        active_event = get_active_event(session)
        json_to_table(
            data=active_event.parameters.model_dump(mode="json"),
            title=f"Event parameters for event: {uuid_shortener(session, active_event) if short else str(active_event.id)}",
            skip_keys=["id", "event_id"],
            common_column_kwargs={"highlight": True},
            column_kwargs={
                "Key": {
                    "header": "Parameter",
                    "justify": "left",
                    "style": TABLE_STYLING.id,
                },
            },
        )
