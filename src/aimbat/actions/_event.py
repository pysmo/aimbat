"""Actions that modify events."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Engine
from sqlmodel import col, select

from aimbat import core
from aimbat.models import AimbatEvent, AimbatPhase

from ._session import open_session, require_ids

__all__ = ["delete_events"]


def delete_events(event_ids: Sequence[UUID], *, engine: Engine | None = None) -> None:
    """Delete events, together with their phases, seismograms and snapshots.

    Args:
        event_ids: IDs of the events to delete.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not an event. Nothing is deleted.
    """
    with open_session(engine) as session:
        ids = require_ids(session, AimbatEvent, event_ids)
        phase_ids = session.exec(
            select(AimbatPhase.id).where(col(AimbatPhase.event_id).in_(ids))
        ).all()
        for event_id in ids:
            core.delete_event(session, event_id)
        session.commit()
    for phase_id in phase_ids:
        core.evict_iccs_cache_entry(phase_id)
