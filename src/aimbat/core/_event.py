"""Query and delete AimbatEvent records."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatEventRead,
    AimbatPhase,
    AimbatPhaseParameters,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
    undefer_counts,
)
from aimbat.utils import check_field_name_flags, dump_models, rel

from ._session import flush_deletes

__all__ = [
    "delete_event",
    "dump_event_table",
    "get_completed_events",
    "get_events_using_station",
    "resolve_event",
]


def _phase_loads() -> tuple[Any, ...]:
    """Loader options for an event's phases with their parameters, quality and rows."""
    phases = selectinload(rel(AimbatEvent.phases))
    return (
        phases.selectinload(rel(AimbatPhase.parameters)),
        phases.selectinload(rel(AimbatPhase.quality)),
        phases.selectinload(rel(AimbatPhase.seismogram_parameters)).selectinload(
            rel(AimbatSeismogramParameters.quality)
        ),
    )


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
    flush_deletes(session)


def get_completed_events(session: Session) -> Sequence[AimbatEvent]:
    """Get the events marked as completed.

    An event counts as completed when it has phases and all of them are.

    Args:
        session: SQL session.

    Returns:
        All events whose phases all have the `completed` parameter set.
    """

    logger.debug("Getting completed events from project.")

    open_events = (
        select(AimbatPhase.event_id)
        .join(AimbatPhaseParameters)
        .where(col(AimbatPhaseParameters.completed).is_(False))
    )
    statement = (
        select(AimbatEvent)
        .where(col(AimbatEvent.id).in_(select(AimbatPhase.event_id)))
        .where(col(AimbatEvent.id).not_in(open_events))
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
        .options(*_phase_loads())
    )

    events = session.exec(statement).all()

    logger.debug(f"Found {len(events)}.")

    return events


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

    statement = select(AimbatEvent).options(*_phase_loads())
    if from_read_model:
        statement = statement.options(*undefer_counts(AimbatEvent))
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
