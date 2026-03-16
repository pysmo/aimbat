"""Get and set the default event (i.e. the one being processed by default)."""

from uuid import UUID

from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat.logger import logger
from aimbat.models import AimbatEvent

__all__ = [
    "get_default_event",
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
        NoResultFound: If an explicit event_id is given but not found.
        NoResultFound: If no event_id is given and no default event is set.
    """
    if event_id:
        logger.debug(f"Resolving event by explicit ID: {event_id}")
        event = session.get(AimbatEvent, event_id)
        if event is None:
            raise NoResultFound(f"No AimbatEvent found with id: {event_id}.")
        return event
    logger.debug("Falling back to default event for resolution.")
    event = get_default_event(session)
    if event is None:
        raise NoResultFound("No event selected.")
    return event


def set_default_event(session: Session, event_id: UUID) -> None:
    """
    Set the default event (i.e. the one being processed).

    Args:
        session: SQL session.
        event_id: UUID of AIMBAT Event to set as default one.
    """

    logger.debug(f"Setting default {event_id=}")

    new_default_event = session.get(AimbatEvent, event_id)
    if new_default_event is None:
        raise ValueError(f"No AimbatEvent found with id: {event_id}.")

    current_default_event = get_default_event(session)

    # unset the current default first
    if current_default_event is not None:
        if new_default_event.id == current_default_event.id:
            return
        current_default_event.is_default = None
        session.add(current_default_event)
        session.flush()

    # set new default
    new_default_event.is_default = True
    session.add(new_default_event)
    session.commit()
