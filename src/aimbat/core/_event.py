"""Module to manage and view events in AIMBAT."""

from collections.abc import Sequence
from typing import Any, Literal, overload
from uuid import UUID

from pandas import Timedelta
from pydantic import TypeAdapter
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat._types import (
    EventParameter,
    EventParameterBool,
    EventParameterFloat,
    EventParameterTimedelta,
)
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatEventParameters,
    AimbatSeismogram,
    AimbatStation,
    _AimbatEventRead,
)
from aimbat.models._parameters import AimbatEventParametersBase

__all__ = [
    "delete_event_by_id",
    "delete_event",
    "get_completed_events",
    "get_events_using_station",
    "get_event_parameter",
    "set_event_parameter",
    "dump_event_table_to_json",
    "dump_event_parameter_table_to_json",
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
        raise NoResultFound(f"Unable to find event using id: {event_id}.")
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


def get_completed_events(session: Session) -> Sequence[AimbatEvent]:
    """Get the events marked as completed.

    Args:
        session: SQL session.
    """

    statement = (
        select(AimbatEvent)
        .join(AimbatEventParameters)
        .where(AimbatEventParameters.completed == 1)
    )

    return session.exec(statement).all()


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

    statement = (
        select(AimbatEvent)
        .join(AimbatSeismogram)
        .join(AimbatStation)
        .where(AimbatStation.id == station.id)
    )

    events = session.exec(statement).all()

    logger.debug(f"Found {len(events)}.")

    return events


@overload
def get_event_parameter(
    session: Session, event: AimbatEvent, name: EventParameterTimedelta
) -> Timedelta: ...


@overload
def get_event_parameter(
    session: Session, event: AimbatEvent, name: EventParameterBool
) -> bool: ...


@overload
def get_event_parameter(
    session: Session, event: AimbatEvent, name: EventParameterFloat
) -> float: ...


@overload
def get_event_parameter(
    session: Session, event: AimbatEvent, name: EventParameter
) -> Timedelta | bool | float: ...


def get_event_parameter(
    session: Session, event: AimbatEvent, name: EventParameter
) -> Timedelta | bool | float:
    """Get event parameter value for the given event.

    Args:
        session: Database session.
        event: AimbatEvent.
        name: Name of the parameter.
    """

    logger.info(f"Getting {name=} value for {event=}.")

    return getattr(event.parameters, name)


@overload
def set_event_parameter(
    session: Session,
    event: AimbatEvent,
    name: EventParameterTimedelta,
    value: Timedelta,
    *,
    validate_iccs: bool = ...,
) -> None: ...


@overload
def set_event_parameter(
    session: Session,
    event: AimbatEvent,
    name: EventParameterFloat,
    value: float,
    *,
    validate_iccs: bool = ...,
) -> None: ...


@overload
def set_event_parameter(
    session: Session,
    event: AimbatEvent,
    name: EventParameterBool,
    value: bool | str,
    *,
    validate_iccs: bool = ...,
) -> None: ...


@overload
def set_event_parameter(
    session: Session,
    event: AimbatEvent,
    name: EventParameter,
    value: Timedelta | bool | float | str,
    *,
    validate_iccs: bool = ...,
) -> None: ...


def set_event_parameter(
    session: Session,
    event: AimbatEvent,
    name: EventParameter,
    value: Timedelta | bool | float | str,
    *,
    validate_iccs: bool = False,
) -> None:
    """Set event parameter value for the given event.

    Args:
        session: Database session.
        event: AimbatEvent.
        name: Name of the parameter.
        value: Value to set.
        validate_iccs: If True, attempt ICCS construction with the new value
            before committing. Raises and leaves the database unchanged on failure.
    """

    logger.info(f"Setting {name=} to {value} for {event=}.")

    parameters = AimbatEventParametersBase.model_validate(
        event.parameters, update={name: value}
    )
    new_value = getattr(parameters, name)

    if validate_iccs:
        from aimbat.core._iccs import validate_iccs_construction

        # Temporarily apply the new value in-memory with autoflush suppressed so
        # the session never writes to the DB during the validation query.
        old_value = getattr(event.parameters, name)
        with session.no_autoflush:
            setattr(event.parameters, name, new_value)
            try:
                validate_iccs_construction(event)
            except Exception as exc:
                setattr(event.parameters, name, old_value)
                raise ValueError(f"ICCS rejected {name}={value}: {exc}") from exc
            setattr(event.parameters, name, old_value)

    setattr(event.parameters, name, new_value)
    session.add(event)
    session.commit()


@overload
def dump_event_table_to_json(
    session: Session, as_string: Literal[True] = ...
) -> str: ...


@overload
def dump_event_table_to_json(
    session: Session, as_string: Literal[False]
) -> list[dict[str, Any]]: ...


def dump_event_table_to_json(
    session: Session, as_string: bool = True
) -> str | list[dict[str, Any]]:
    """Dump the table data to json."""

    logger.info("Dumping AIMBAT event table to json.")
    events = session.exec(select(AimbatEvent)).all()
    event_reads = [_AimbatEventRead.from_event(e) for e in events]
    adapter: TypeAdapter[Sequence[_AimbatEventRead]] = TypeAdapter(
        Sequence[_AimbatEventRead]
    )
    if as_string:
        return adapter.dump_json(event_reads).decode("utf-8")
    return adapter.dump_python(event_reads, mode="json")


@overload
def dump_event_parameter_table_to_json(
    session: Session,
    all_events: bool,
    as_string: Literal[True],
    event: AimbatEvent | None = None,
) -> str: ...


@overload
def dump_event_parameter_table_to_json(
    session: Session,
    all_events: Literal[False],
    as_string: Literal[False],
    event: AimbatEvent | None = None,
) -> dict[str, Any]: ...


@overload
def dump_event_parameter_table_to_json(
    session: Session,
    all_events: Literal[True],
    as_string: Literal[False],
    event: AimbatEvent | None = None,
) -> list[dict[str, Any]]: ...


def dump_event_parameter_table_to_json(
    session: Session,
    all_events: bool,
    as_string: bool,
    event: AimbatEvent | None = None,
) -> str | dict[str, Any] | list[dict[str, Any]]:
    """Dump the event parameter table data to json.

    Args:
        session: Database session.
        all_events: Include event parameter table data for all events.
        as_string: Whether to return the result as a string.
        event: Event to dump parameter data for (only used when all_events is False).
    """

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

    if event is None:
        raise ValueError("An event must be provided when all_events is False.")

    if as_string:
        return event.parameters.model_dump_json()
    return event.parameters.model_dump(mode="json")
