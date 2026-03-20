"""Module to manage and view events in AIMBAT."""

from collections.abc import Sequence
from typing import Any, Literal, overload
from uuid import UUID

from pandas import Timedelta
from pydantic import TypeAdapter
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from aimbat._types import EventParameter
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatEventParameters,
    AimbatEventRead,
    AimbatSeismogram,
    AimbatStation,
    SeismogramQualityStats,
)
from aimbat.models._parameters import AimbatEventParametersBase
from aimbat.utils import get_title_map, rel

__all__ = [
    "delete_event",
    "get_completed_events",
    "get_event_quality",
    "get_events_using_station",
    "resolve_event",
    "set_event_parameter",
    "dump_event_table",
    "dump_event_parameter_table",
    "dump_event_quality_table",
]


def resolve_event(session: Session, event_id: UUID | None = None) -> AimbatEvent:
    """Resolve an event from an explicit ID.

    Args:
        session: SQL session.
        event_id: Optional event ID.

    Returns:
        The specified event.

    Raises:
        NoResultFound: If an explicit event_id is given but not found.
        NoResultFound: If no event_id is given.
    """
    if event_id:
        logger.debug(f"Resolving event by explicit ID: {event_id}")
        event = session.get(AimbatEvent, event_id)
        if event is None:
            raise NoResultFound(f"No AimbatEvent found with id: {event_id}.")
        return event

    raise NoResultFound("No event specified.")


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

    Returns:
        All events where the `completed` parameter is set.
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
        .options(
            selectinload(rel(AimbatEvent.seismograms)).selectinload(
                rel(AimbatSeismogram.parameters)
            ),
            selectinload(rel(AimbatEvent.parameters)),
            selectinload(rel(AimbatEvent.quality)),
        )
    )

    events = session.exec(statement).all()

    logger.debug(f"Found {len(events)}.")

    return events


def get_event_quality(session: Session, event_id: UUID) -> SeismogramQualityStats:
    """Get aggregated quality statistics for an event.

    Args:
        session: Database session.
        event_id: UUID of the event.

    Returns:
        Aggregated seismogram quality statistics.

    Raises:
        NoResultFound: If no event with the given ID is found.
    """
    logger.debug(f"Getting quality stats for event {event_id}.")

    event = session.exec(
        select(AimbatEvent)
        .where(AimbatEvent.id == event_id)
        .options(
            selectinload(rel(AimbatEvent.seismograms)).selectinload(
                rel(AimbatSeismogram.quality)
            ),
            selectinload(rel(AimbatEvent.quality)),
        )
    ).one_or_none()

    if event is None:
        raise NoResultFound(f"No AimbatEvent found with id: {event_id}.")

    return SeismogramQualityStats.from_event(event)


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

    statement = select(AimbatEvent).options(
        selectinload(rel(AimbatEvent.seismograms)).selectinload(
            rel(AimbatSeismogram.parameters)
        ),
        selectinload(rel(AimbatEvent.parameters)),
        selectinload(rel(AimbatEvent.quality)),
    )
    events = session.exec(statement).all()

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

    event = session.exec(
        select(AimbatEvent)
        .where(AimbatEvent.id == event_id)
        .options(
            selectinload(rel(AimbatEvent.parameters)),
            selectinload(rel(AimbatEvent.seismograms)).selectinload(
                rel(AimbatSeismogram.parameters)
            ),
        )
    ).one_or_none()
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


def dump_event_quality_table(
    session: Session,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Dump event quality statistics to json.

    Args:
        session: Database session.
        by_alias: Whether to use serialization aliases for the field names.
        by_title: Whether to use the field title metadata for the field names.
            Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event ID to filter by (if none is provided, quality for all
            events is dumped).

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """

    logger.debug("Dumping AIMBAT event quality table to json.")

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    exclude = (exclude or set()) | {"station_id", "snapshot_id"}
    exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    statement = select(AimbatEvent).options(
        selectinload(rel(AimbatEvent.seismograms)).selectinload(
            rel(AimbatSeismogram.quality)
        ),
        selectinload(rel(AimbatEvent.quality)),
    )
    if event_id is not None:
        statement = statement.where(AimbatEvent.id == event_id)

    events = session.exec(statement).all()
    stats = [SeismogramQualityStats.from_event(e) for e in events]

    adapter: TypeAdapter[Sequence[SeismogramQualityStats]] = TypeAdapter(
        Sequence[SeismogramQualityStats]
    )
    data = adapter.dump_python(stats, mode="json", exclude=exclude, by_alias=by_alias)

    if by_title:
        title_map = get_title_map(SeismogramQualityStats)
        return [{title_map.get(k, k): v for k, v in row.items()} for row in data]

    return data
