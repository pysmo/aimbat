"""Get and set the active event (i.e. the one being processed)."""

# WARNING: Do not import other modules from `aimbat.core` here to avoid circular imports
from aimbat.logger import logger
from aimbat.models import AimbatEvent
from aimbat.cli._common import HINTS
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from uuid import UUID

__all__ = [
    "get_active_event",
    "set_active_event_by_id",
    "set_active_event",
]


def get_active_event(session: Session) -> AimbatEvent:
    """
    Return the currently active event (i.e. the one being processed).

    Args:
        session: SQL session.

    Returns:
        Active Event

    Raises
        NoResultFound: When no event is active.
    """

    logger.debug("Attempting to determine active event.")

    select_active_event = select(AimbatEvent).where(AimbatEvent.active == 1)

    # NOTE: While there technically can be no active event in the database,
    # we typically don't really want to go beyond this point when that is the
    # case. Hence we call `one` rather than `one_or_none`.
    try:
        active_event = session.exec(select_active_event).one()
    except NoResultFound:
        raise NoResultFound(f"No active event found. {HINTS.ACTIVATE_EVENT}")

    logger.debug(f"Active event: {active_event.id}")

    return active_event


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
