"""Actions that modify events."""

from collections.abc import Mapping, Sequence
from uuid import UUID

from pandas import Timedelta
from sqlalchemy import Engine

from aimbat import core
from aimbat.models import AimbatEvent
from aimbat.types import EventParameter

from ._session import discard_cached_iccs_on_failure, open_session, require_ids

__all__ = ["delete_events", "set_event_parameters", "toggle_event_completed"]


def delete_events(event_ids: Sequence[UUID], *, engine: Engine | None = None) -> None:
    """Delete events, together with their seismograms and snapshots.

    Args:
        event_ids: IDs of the events to delete.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not an event. Nothing is deleted.
    """
    with open_session(engine) as session:
        ids = require_ids(session, AimbatEvent, event_ids)
        for event_id in ids:
            core.delete_event(session, event_id)
        session.commit()
    for event_id in ids:
        core.evict_iccs_cache_entry(event_id)


def set_event_parameters(
    event_id: UUID,
    values: Mapping[EventParameter, Timedelta | bool | float | int | str],
    *,
    validate_iccs: bool = False,
    engine: Engine | None = None,
) -> None:
    """Set several parameters of an event, validated as a group.

    Args:
        event_id: ID of the event.
        values: New value for each parameter, keyed by parameter name.
        validate_iccs: If True, verify that an ICCS instance can be built
            with the new values before storing them.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the event does not exist.
        ValidationError: If any value is invalid. Nothing is changed.
        IccsValidationError: If `validate_iccs` is True and no ICCS instance
            can be built with the new values. Nothing is changed.
    """
    with discard_cached_iccs_on_failure(event_id), open_session(engine) as session:
        core.set_event_parameters(
            session, event_id, values, validate_iccs=validate_iccs
        )
        session.commit()


def toggle_event_completed(event_id: UUID, *, engine: Engine | None = None) -> bool:
    """Toggle the `completed` flag of an event.

    Args:
        event_id: ID of the event.
        engine: Engine to use. Defaults to the project engine.

    Returns:
        The new value of the flag.

    Raises:
        NoResultFound: If the event does not exist.
    """
    with open_session(engine) as session:
        completed = core.toggle_event_completed(session, event_id)
        session.commit()
    return completed
