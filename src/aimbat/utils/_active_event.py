from aimbat.logger import logger
from aimbat.models import AimbatEvent
from aimbat.cli.common import HINTS
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound

__all__ = ["get_active_event"]


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
