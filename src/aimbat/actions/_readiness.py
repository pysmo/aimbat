"""Actions that check whether the data are ready for processing."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import Engine
from sqlmodel import col, select

from aimbat import core
from aimbat.core import ReadinessItem
from aimbat.models import AimbatEvent, AimbatPhase

from ._session import open_session

__all__ = ["ReadinessReport", "check_data"]


@dataclass(frozen=True)
class ReadinessReport:
    """Readiness items found by `check_data`."""

    items: list[ReadinessItem]
    """Every item found, blocking items and notices."""
    events: int
    """Number of events checked."""
    phases: int
    """Number of phases checked."""

    @property
    def blocking(self) -> list[ReadinessItem]:
        """The items that prevent processing."""
        return [item for item in self.items if item.blocking]


def check_data(
    event_id: UUID | Literal["all"] = "all",
    *,
    phase_name: str | None = None,
    engine: Engine | None = None,
) -> ReadinessReport:
    """Find what prevents or may affect the processing of the project's phases.

    Changes nothing. Checking an initial pick against the end of its
    seismogram reads the seismogram's data.

    Args:
        event_id: Event to check, or `"all"` for every event and the picks
            that belong to no event.
        phase_name: Only the items of phases of this name, whether the
            phase exists or not, and the items covering every phase of an
            event that has a phase of this name. Items of the project are
            left out.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the event does not exist.
    """
    with open_session(engine) as session:
        statement = (
            select(AimbatPhase)
            .join(AimbatEvent)
            .order_by(col(AimbatEvent.time), col(AimbatPhase.name))
        )
        if event_id == "all":
            items = core.readiness(session)
            events = len(session.exec(select(AimbatEvent.id)).all())
        else:
            session.get_one(AimbatEvent, event_id)
            statement = statement.where(col(AimbatPhase.event_id) == event_id)
            items = core.readiness(session, event_id=event_id)
            events = 1

        if phase_name is not None:
            statement = statement.where(col(AimbatPhase.name) == phase_name)
        phases = list(session.exec(statement).all())

        if phase_name is not None:
            with_phase = {p.event_id for p in phases}
            items = [
                item
                for item in items
                if item.event_id is not None
                and (
                    item.phase_name == phase_name
                    or (item.phase_name is None and item.event_id in with_phase)
                )
            ]
        return ReadinessReport(items, events=events, phases=len(phases))
