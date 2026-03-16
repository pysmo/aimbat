"""Module to manage and view events in AIMBAT."""

from collections.abc import Sequence
from typing import Any, Literal, overload
from uuid import UUID

from pandas import Timedelta
from pydantic import TypeAdapter
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat._types import EventParameter
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatEventParameters,
    AimbatEventRead,
    AimbatSeismogram,
    AimbatStation,
)
from aimbat.models._parameters import AimbatEventParametersBase
from aimbat.utils import get_title_map

__all__ = [
    "delete_event",
    "get_completed_events",
    "get_events_using_station",
    "set_event_parameter",
    "dump_event_table",
    "dump_event_parameter_table",
]

type EventParameterBool = Literal[
    EventParameter.COMPLETED, EventParameter.BANDPASS_APPLY
]
type EventParameterFloat = Literal[
    EventParameter.MIN_CC,
    EventParameter.BANDPASS_FMIN,
    EventParameter.BANDPASS_FMAX,
    EventParameter.RAMP_WIDTH,
]
type EventParameterTimedelta = Literal[
    EventParameter.WINDOW_PRE, EventParameter.WINDOW_POST
]


def delete_event(session: Session, event_id: UUID) -> None:
    """Delete an AimbatEvent from the database.

    Args:
        session: Database session.
        event_id: Event ID.

    """

    logger.info(f"Deleting event {event_id}.")

    event = session.get(AimbatEvent, event_id)
    if event is None:
        raise NoResultFound(f"Unable to find event using id: {event_id}.")

    session.delete(event)
    session.commit()


def get_completed_events(session: Session) -> Sequence[AimbatEvent]:
    """Get the events marked as completed.

    Args:
        session: SQL session.
    """

    logger.debug("Getting completed events from project.")

    statement = (
        select(AimbatEvent)
        .join(AimbatEventParameters)
        .where(AimbatEventParameters.completed == 1)
    )

    return session.exec(statement).all()


def get_events_using_station(
    session: Session, station_id: UUID
) -> Sequence[AimbatEvent]:
    """Get all events that use a particular station.

    Args:
        session: Database session.
        station_id: UUID of the station to return events for.

    Returns: Events that use the station.
    """

    logger.debug(f"Getting events for station: {station_id}.")

    statement = (
        select(AimbatEvent)
        .join(AimbatSeismogram)
        .join(AimbatStation)
        .where(AimbatStation.id == station_id)
    )

    events = session.exec(statement).all()

    logger.debug(f"Found {len(events)}.")

    return events


@overload
def set_event_parameter(
    session: Session,
    event_id: UUID,
    name: EventParameterTimedelta,
    value: Timedelta,
    *,
    validate_iccs: bool = ...,
) -> None: ...


@overload
def set_event_parameter(
    session: Session,
    event_id: UUID,
    name: EventParameterFloat,
    value: float,
    *,
    validate_iccs: bool = ...,
) -> None: ...


@overload
def set_event_parameter(
    session: Session,
    event_id: UUID,
    name: EventParameterBool,
    value: bool | str,
    *,
    validate_iccs: bool = ...,
) -> None: ...


@overload
def set_event_parameter(
    session: Session,
    event_id: UUID,
    name: EventParameter,
    value: Timedelta | bool | float | str,
    *,
    validate_iccs: bool = ...,
) -> None: ...


def set_event_parameter(
    session: Session,
    event_id: UUID,
    name: EventParameter,
    value: Timedelta | bool | float | str,
    *,
    validate_iccs: bool = False,
) -> None:
    """Set event parameter value for the given event.

    Args:
        session: Database session.
        event_id: UUID of the event to set the parameter value for.
        name: Name of the parameter.
        value: Value to set.
        validate_iccs: If True, attempt ICCS construction with the new value
            before committing. Raises and leaves the database unchanged on failure.
    """
    from ._iccs import clear_mccc_quality
    from ._snapshot import compute_parameters_hash, sync_from_matching_hash

    logger.debug(f"Setting {name=} to {value} for event {event_id=}.")

    event = session.get(AimbatEvent, event_id)
    if event is None:
        raise NoResultFound(f"No AimbatEvent found with id: {event_id}.")

    # Perform Pydantic validation (including optional ICCS validation)
    parameters = AimbatEventParametersBase.model_validate(
        event.parameters,
        update={name: value},
        context={"validate_iccs": validate_iccs, "event": event},
    )

    setattr(event.parameters, name, getattr(parameters, name))
    session.add(event)
    parameters_hash = compute_parameters_hash(event)
    if not sync_from_matching_hash(session, parameters_hash):
        clear_mccc_quality(session, event)


@overload
def dump_event_table(
    session: Session,
    from_read_model: Literal[False] = ...,
    by_alias: bool = ...,
    by_title: bool = ...,
    exclude: set[str] | None = ...,
) -> str: ...


@overload
def dump_event_table(
    session: Session,
    from_read_model: Literal[True],
    by_alias: bool = ...,
    by_title: bool = ...,
    exclude: set[str] | None = ...,
) -> list[dict[str, Any]]: ...


def dump_event_table(
    session: Session,
    from_read_model: bool = False,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]] | str:
    """Dump the table data to json serialisable list of dicts.

    Args:
        session: Database session.
        from_read_model: Whether to dump from the read model (True) or the ORM model.
        by_alias: Whether to use serialization aliases for the field names.
        by_title: Whether to use the field title metadata for the field names in the
            output (only applicable when from_read_model is True). Mutually
            exclusive with by_alias.
        exclude: Set of field names to exclude from the output.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
        ValueError: If `by_title` is True but `from_read_model` is False.
    """
    logger.debug("Dumping AIMBAT event table to json.")

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    if not from_read_model and by_title:
        raise ValueError("'by_title' is only supported when 'from_read_model' is True.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    events = session.exec(select(AimbatEvent)).all()

    if from_read_model:
        event_reads = [AimbatEventRead.from_event(e, session=session) for e in events]
        adapter_reads: TypeAdapter[Sequence[AimbatEventRead]] = TypeAdapter(
            Sequence[AimbatEventRead]
        )
        data = adapter_reads.dump_python(
            event_reads, exclude=exclude, by_alias=by_alias, mode="json"
        )

        if by_title:
            title_map = get_title_map(AimbatEventRead)
            return [{title_map.get(k, k): v for k, v in row.items()} for row in data]

        return data

    adapter: TypeAdapter[Sequence[AimbatEvent]] = TypeAdapter(Sequence[AimbatEvent])
    return adapter.dump_json(events, exclude=exclude, by_alias=by_alias).decode()


def dump_event_parameter_table(
    session: Session,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Dump the event parameter table data to json.

    Args:
        session: Database session.
        by_alias: Whether to use serialization aliases for the field names.
        by_title: Whether to use the field title metadata for the field names.
            Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event ID to filter parameters by (if none is provided,
            parameters for all events are dumped).

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """

    logger.debug("Dumping AIMBAT event parameter table to json.")

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    adapter: TypeAdapter[Sequence[AimbatEventParameters]] = TypeAdapter(
        Sequence[AimbatEventParameters]
    )

    if event_id is not None:
        statement = select(AimbatEventParameters).where(
            AimbatEventParameters.event_id == event_id
        )
    else:
        statement = select(AimbatEventParameters)

    parameters = session.exec(statement).all()

    data = adapter.dump_python(
        parameters, mode="json", exclude=exclude, by_alias=by_alias
    )

    if by_title:
        title_map = get_title_map(AimbatEventParameters)
        return [{title_map.get(k, k): v for k, v in row.items()} for row in data]

    return data
