"""Get and set the default event (i.e. the one being processed by default)."""

from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from uuid import UUID
from aimbat.logger import logger
from aimbat.models import AimbatEvent

__all__ = [
    "get_default_event",
    "set_default_event_by_id",
    "set_default_event",
    "resolve_event",
]


def get_default_event(session: Session) -> AimbatEvent | None:
    """
    Return the currently default event, or None if no event is set as default.

    Args:
        session: SQL session.

    Returns:
        Default Event, or None.
    """

    logger.debug("Attempting to determine default event.")

    statement = select(AimbatEvent).where(AimbatEvent.is_default == 1)
    default_event = session.exec(statement).one_or_none()

    logger.debug(f"Default event: {default_event.id if default_event else None}")

    return default_event


def resolve_event(session: Session, event_id: UUID | None = None) -> AimbatEvent:
    """
    Resolve an event from either an explicit ID or the default event.

    Args:
        session: SQL session.
        event_id: Optional event ID.

    Returns:
        The specified event or the default event.

    Raises:
        ValueError: If an explicit event_id is given but not found.
        NoResultFound: If no event_id is given and no default event is set.
    """
    if event_id:
        logger.debug(f"Resolving event by explicit ID: {event_id}")
        event = session.get(AimbatEvent, event_id)
        if event is None:
            raise ValueError(f"No AimbatEvent found with id: {event_id}.")
        return event
    event = get_default_event(session)
    if event is None:
        raise NoResultFound("No default event found.")
    return event


def set_default_event_by_id(session: Session, event_id: UUID) -> None:
    """
    Set the currently selected event (i.e. the one being processed) by its ID.

    Args:
        session: SQL session.
        event_id: ID of AIMBAT Event to set as default one.

    Raises:
        ValueError: If no event with the given ID is found.
    """
    logger.info(f"Setting default event to event with id={event_id}.")

    if event_id not in session.exec(select(AimbatEvent.id)).all():
        raise ValueError(f"No AimbatEvent found with id: {event_id}.")

    aimbat_event = session.exec(
        select(AimbatEvent).where(AimbatEvent.id == event_id)
    ).one()
    set_default_event(session, aimbat_event)


def set_default_event(session: Session, event: AimbatEvent) -> None:
    """
    Set the default event (i.e. the one being processed).

    Args:
        session: SQL session.
        event: AIMBAT Event to set as default.
    """

    logger.info(f"Setting default {event=}")

    current = get_default_event(session)
    if current is not None and event.id == current.id:
        return

    event.is_default = True
    session.add(event)
    session.commit()
