"""Actions that align the seismograms of a phase with ICCS or MCCC.

AIMBAT keeps one ICCS instance per phase in memory and reuses it while the
phase's parameters are unchanged, so repeated calls do not rebuild it. A
phase with blocking readiness items (see `aimbat data check`) is refused.
`aimbat.core.create_iccs_instance` does not check readiness.
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


def prepare_iccs(phase_id: UUID, *, engine: Engine | None = None) -> BoundICCS:
    """Return an up-to-date ICCS instance for a phase, building one if needed.

    Building an instance computes and stores the CC value of each seismogram
    with the stack. The same instance is returned to later calls while the
    phase's parameters are unchanged, so changes made to it are seen by every
    caller.

    Args:
        phase_id: ID of the phase.
        engine: Engine to use. Defaults to the project engine.

    Returns:
        The ICCS instance, bound to its phase.

    Raises:
        NoResultFound: If the phase does not exist.
        NotReadyError: If blocking readiness items apply to the phase, which
            includes a phase with no seismograms.
    """
    with open_session(engine) as session:
        core.require_ready(session, phase_id)
        bound = core.create_iccs_instance(session, phase_id)
        session.commit()
    return bound


def run_iccs(
    phase_id: UUID,
    *,
    autoflip: bool = False,
    autoselect: bool = False,
    engine: Engine | None = None,
) -> AlignRun[IccsResult]:
    """Align the seismograms of a phase with ICCS and store the refined picks.

    Args:
        phase_id: ID of the phase.
        autoflip: If True, flip seismograms whose CC with the stack is
            negative.
        autoselect: If True, deselect seismograms whose CC falls below
            `min_cc`, and select them again once it exceeds `min_cc`.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the phase does not exist.
        NotReadyError: If blocking readiness items apply to the phase, which
            includes a phase with no seismograms.
    """
    with open_session(engine) as session:
        core.require_ready(session, phase_id)
        iccs = core.create_iccs_instance(session, phase_id).iccs
        result = core.run_iccs(session, phase_id, iccs, autoflip, autoselect)
        session.commit()
        summary = core.summarise_iccs_result(result, len(iccs.seismograms))
    return AlignRun(result=result, summary=summary)


def run_mccc(
    phase_id: UUID,
    *,
    all_seismograms: bool = False,
    engine: Engine | None = None,
) -> AlignRun[McccResult]:
    """Refine the picks of a phase with MCCC and store them.

    Args:
        phase_id: ID of the phase.
        all_seismograms: If True, include deselected seismograms.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the phase does not exist.
        NotReadyError: If blocking readiness items apply to the phase, which
            includes a phase with no seismograms.
    """
    with open_session(engine) as session:
        core.require_ready(session, phase_id)
        iccs = core.create_iccs_instance(session, phase_id).iccs
        result = core.run_mccc(session, phase_id, iccs, all_seismograms)
        session.commit()
    return AlignRun(result=result, summary=core.summarise_mccc_result(result))
