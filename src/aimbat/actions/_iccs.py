"""Actions that align the seismograms of an event with ICCS or MCCC.

AIMBAT keeps one ICCS instance per event in memory and reuses it while the
event's parameters are unchanged, so repeated calls do not rebuild it.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Engine

from pysmo.tools.iccs import IccsResult, McccResult

from aimbat import core
from aimbat.core import BoundICCS, RunSummary

from ._session import open_session

__all__ = ["AlignRun", "prepare_iccs", "run_iccs", "run_mccc"]


@dataclass(frozen=True)
class AlignRun[R: (IccsResult, McccResult)]:
    """Result of an ICCS or MCCC run, with a summary for display."""

    result: R
    """Result returned by pysmo."""

    summary: RunSummary
    """Description of the outcome of the run."""


def prepare_iccs(event_id: UUID, *, engine: Engine | None = None) -> BoundICCS:
    """Return an up-to-date ICCS instance for an event, building one if needed.

    Building an instance computes and stores the CC value of each seismogram
    with the stack. The same instance is returned to later calls while the
    event's parameters are unchanged, so changes made to it are seen by every
    caller.

    Args:
        event_id: ID of the event.
        engine: Engine to use. Defaults to the project engine.

    Returns:
        The ICCS instance, bound to its event.

    Raises:
        NoResultFound: If the event does not exist.
        NoSeismogramsError: If the event has no seismograms.
    """
    with open_session(engine) as session:
        event = core.resolve_event(session, event_id)
        bound = core.create_iccs_instance(session, event)
        session.commit()
    return bound


def run_iccs(
    event_id: UUID,
    *,
    autoflip: bool = False,
    autoselect: bool = False,
    engine: Engine | None = None,
) -> AlignRun[IccsResult]:
    """Align the seismograms of an event with ICCS and store the refined picks.

    Args:
        event_id: ID of the event.
        autoflip: If True, flip seismograms whose CC with the stack is
            negative.
        autoselect: If True, deselect seismograms whose CC falls below
            `min_cc`, and select them again once it exceeds `min_cc`.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the event does not exist.
    """
    with open_session(engine) as session:
        event = core.resolve_event(session, event_id)
        iccs = core.create_iccs_instance(session, event).iccs
        result = core.run_iccs(session, event, iccs, autoflip, autoselect)
        session.commit()
        summary = core.summarise_iccs_result(result, len(iccs.seismograms))
    return AlignRun(result=result, summary=summary)


def run_mccc(
    event_id: UUID,
    *,
    all_seismograms: bool = False,
    engine: Engine | None = None,
) -> AlignRun[McccResult]:
    """Refine the picks of an event with MCCC and store them.

    Args:
        event_id: ID of the event.
        all_seismograms: If True, include deselected seismograms.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the event does not exist.
    """
    with open_session(engine) as session:
        event = core.resolve_event(session, event_id)
        iccs = core.create_iccs_instance(session, event).iccs
        result = core.run_mccc(session, event, iccs, all_seismograms)
        session.commit()
    return AlignRun(result=result, summary=core.summarise_mccc_result(result))
