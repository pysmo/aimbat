"""Query, update, and delete AimbatEvent records, their parameters, and their quality statistics."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal, overload
from uuid import UUID

from pandas import Timedelta
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatEventParameters,
    AimbatEventRead,
    AimbatSeismogram,
    AimbatStation,
    SeismogramQualityStats,
    undefer_counts,
)
from aimbat.models._parameters import AimbatEventParametersBase
from aimbat.types import EventParameter
from aimbat.utils import check_field_name_flags, dump_models, rel

__all__ = [
    "delete_event",
    "dump_event_parameter_table",
    "dump_event_quality_table",
    "dump_event_table",
    "get_completed_events",
    "get_event_quality",
    "get_events_using_station",
    "resolve_event",
    "set_event_parameter",
    "set_event_parameters",
    "toggle_event_completed",
]


def resolve_event(session: Session, event_id: UUID | None = None) -> AimbatEvent:
    """Resolve an event from an explicit ID.

    Args:
        session: SQL session.
        event_id: Optional event ID.

    Returns:
        The specified event.

    Raises:
        NoResultFound: If `event_id` is not given, or if no event with the
            given `event_id` exists.
    """
    if event_id is not None:
        logger.debug(f"Resolving event by explicit ID: {event_id}.")
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
type EventParameterInt = Literal[EventParameter.CORNERS]
type EventParameterTimedelta = Literal[
    EventParameter.WINDOW_PRE, EventParameter.WINDOW_POST
]


def delete_event(session: Session, event_id: UUID) -> None:
    """Delete an AimbatEvent from the database.

    Args:
        session: Database session.
        event_id: Event ID.

    Raises:
        NoResultFound: If no event with the given ID is found.
    """

    logger.info(f"Deleting event {event_id}.")

    event = session.get(AimbatEvent, event_id)
    if event is None:
        raise NoResultFound(f"Unable to find event using id: {event_id}.")

    session.delete(event)
    session.commit()

    from ._iccs import evict_iccs_cache_entry

    evict_iccs_cache_entry(event_id)


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
        .where(col(AimbatEventParameters.completed).is_(True))
    )

    return session.exec(statement).all()


def get_events_using_station(
    session: Session, station_id: UUID
) -> Sequence[AimbatEvent]:
    """Get all events that use a particular station.

    Args:
        session: Database session.
        station_id: UUID of the station to return events for.

    Returns:
        Events that use the station.
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


def toggle_event_completed(session: Session, event_id: UUID) -> bool:
    """Flip the `completed` flag on an event's parameters.

    `completed` is excluded from the parameters hash used for snapshot
    matching (it does not affect seismogram processing), so this does not
    go through `set_event_parameter`'s snapshot-sync/MCCC-invalidation path.

    Args:
        session: Database session.
        event_id: UUID of the event to toggle.

    Returns:
        The new value of the `completed` flag.

    Raises:
        NoResultFound: If no event with the given ID is found.
    """
    logger.debug(f"Toggling completed flag for event {event_id}.")

    event = session.get(AimbatEvent, event_id)
    if event is None:
        raise NoResultFound(f"No AimbatEvent found with id: {event_id}.")

    event.parameters.completed = not event.parameters.completed
    session.add(event)
    session.commit()
    return event.parameters.completed


def get_event_quality(session: Session, event_id: UUID) -> SeismogramQualityStats:
    """Get aggregated quality statistics for an event.

    Args:
        session: Database session.
        event_id: UUID of the event.

    Returns:
        Aggregated seismogram quality statistics. The `mccc_rmse` field is
        taken from the event-level quality record rather than the per-seismogram
        records, and is `None` if MCCC has not been run.

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


def dump_event_table(
    session: Session,
    from_read_model: bool = False,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Dump the table data to a JSON-serialisable list of dicts.

    Args:
        session: Database session.
        from_read_model: Whether to dump from the read model (True) or the ORM model.
        by_alias: Whether to use serialisation aliases for the field names.
        by_title: Whether to use the field title metadata for the field names in the
            output (only applicable when from_read_model is True). Mutually
            exclusive with by_alias.
        exclude: Set of field names to exclude from the output.

    Returns:
        A list of dicts, one per event.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
        ValueError: If `by_title` is True but `from_read_model` is False.
    """
    logger.debug("Dumping AIMBAT event table to json.")

    check_field_name_flags(by_alias, by_title, from_read_model)

    statement = select(AimbatEvent).options(
        selectinload(rel(AimbatEvent.seismograms)).selectinload(
            rel(AimbatSeismogram.parameters)
        ),
        selectinload(rel(AimbatEvent.parameters)),
        selectinload(rel(AimbatEvent.quality)),
        *undefer_counts(AimbatEvent),
    )
    events = session.exec(statement).all()

    if from_read_model:
        event_reads = [AimbatEventRead.from_event(e, session=session) for e in events]
        return dump_models(
            event_reads,
            AimbatEventRead,
            by_alias=by_alias,
            by_title=by_title,
            exclude=exclude,
        )

    return dump_models(events, AimbatEvent, by_alias=by_alias, exclude=exclude)


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
    name: EventParameterInt,
    value: int,
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
    value: Timedelta | bool | float | int | str,
    *,
    validate_iccs: bool = ...,
) -> None: ...


def set_event_parameter(
    session: Session,
    event_id: UUID,
    name: EventParameter,
    value: Timedelta | bool | float | int | str,
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

    Raises:
        NoResultFound: If no event with the given ID is found.
        ValidationError: If `value` fails Pydantic validation for `name`.
        IccsValidationError: If `validate_iccs` is True and ICCS construction
            is rejected by the new value.
    """
    set_event_parameters(session, event_id, {name: value}, validate_iccs=validate_iccs)


def set_event_parameters(
    session: Session,
    event_id: UUID,
    values: Mapping[EventParameter, Timedelta | bool | float | int | str],
    *,
    validate_iccs: bool = False,
) -> None:
    """Set several event parameters at once, validated as a group.

    The whole update is validated against the merged parameter state, so a
    combination of values that no single-field order could reach (e.g. a new
    `bandpass_fmin` above the old `bandpass_fmax` alongside the new
    `bandpass_fmax`) is accepted.

    Args:
        session: Database session.
        event_id: UUID of the event to update.
        values: Parameter name -> new value. An empty mapping is a no-op.
        validate_iccs: If True, attempt ICCS construction with the new values
            before committing. Raises and leaves the database unchanged on failure.

    Raises:
        NoResultFound: If no event with the given ID is found.
        ValidationError: If any value fails Pydantic validation.
        IccsValidationError: If `validate_iccs` is True and ICCS construction
            is rejected by the new values.
    """
    from ._iccs import validate_iccs_construction
    from ._snapshot import resync_quality

    updates = {str(name): value for name, value in values.items()}
    logger.debug(f"Setting {updates} for event {event_id=}.")

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

    if not updates:
        return

    parameters = AimbatEventParametersBase.model_validate(
        event.parameters,
        update=updates,
    )

    if validate_iccs:
        validate_iccs_construction(event, parameters=parameters)

    for name in updates:
        setattr(event.parameters, name, getattr(parameters, name))
    session.add(event)
    resync_quality(session, event)


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
        by_alias: Whether to use serialisation aliases for the field names.
        by_title: Whether to use the field title metadata for the field names.
            Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event ID to filter parameters by (if none is provided,
            parameters for all events are dumped).

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """

    logger.debug("Dumping AIMBAT event parameter table to json.")

    check_field_name_flags(by_alias, by_title)

    if event_id is not None:
        statement = select(AimbatEventParameters).where(
            AimbatEventParameters.event_id == event_id
        )
    else:
        statement = select(AimbatEventParameters)

    parameters = session.exec(statement).all()

    return dump_models(
        parameters,
        AimbatEventParameters,
        by_alias=by_alias,
        by_title=by_title,
        exclude=exclude,
    )


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
        by_alias: Whether to use serialisation aliases for the field names.
        by_title: Whether to use the field title metadata for the field names.
            Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event ID to filter by (if none is provided, quality for all
            events is dumped).

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """

    logger.debug("Dumping AIMBAT event quality table to json.")

    check_field_name_flags(by_alias, by_title)

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

    return dump_models(
        stats,
        SeismogramQualityStats,
        by_alias=by_alias,
        by_title=by_title,
        exclude=(exclude or set()) | {"station_id", "snapshot_id"},
    )
