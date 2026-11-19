"""Actions that modify phases."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from uuid import UUID

from pandas import Timedelta, Timestamp
from sqlalchemy import Engine

from aimbat import core
from aimbat.types import PhaseParameter

from ._session import discard_cached_iccs_on_failure, open_session

__all__ = [
    "RemovePhaseResult",
    "remove_phase",
    "rename_phase",
    "set_phase_parameters",
    "toggle_phase_completed",
]


@dataclass(frozen=True)
class RemovePhaseResult:
    """What `remove_phase` deleted, or would delete when shown to `confirm`."""

    event_id: UUID
    event_time: Timestamp
    phase_name: str
    rows: int
    """Rows of the phase."""
    snapshots: int
    """Snapshots of the phase."""
    dismissed_picks: int
    """Picks of the event named for the phase that are dismissed."""
    removed: bool
    """Whether the phase was deleted."""


def remove_phase(
    phase_id: UUID,
    *,
    confirm: Callable[[RemovePhaseResult], bool] | None = None,
    engine: Engine | None = None,
) -> RemovePhaseResult:
    """Delete a phase, and dismiss the picks of its event named for it.

    The rows, parameters, quality and snapshots of the phase are deleted
    with it. The dismissed picks are kept, and `restore_picks` undoes the
    dismissal.

    Args:
        phase_id: ID of the phase.
        confirm: Callback that receives the pending deletion before it is
            saved. Deletion proceeds only if it returns True.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the phase does not exist.
    """
    with open_session(engine) as session:
        report = core.remove_phase(session, phase_id)
        result = RemovePhaseResult(
            event_id=report.event_id,
            event_time=report.event_time,
            phase_name=report.phase_name,
            rows=report.rows,
            snapshots=report.snapshots,
            dismissed_picks=report.dismissed_picks,
            removed=False,
        )
        if confirm is not None and not confirm(result):
            session.rollback()
            return result
        session.commit()
    core.evict_iccs_cache_entry(phase_id)
    return replace(result, removed=True)


def rename_phase(phase_id: UUID, name: str, *, engine: Engine | None = None) -> None:
    """Rename a phase, and the picks of its event named for it.

    Args:
        phase_id: ID of the phase.
        name: New name.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the phase does not exist.
        ValueError: If the name is not a valid phase name, or another phase
            of the event already has it. Nothing is changed.
    """
    with open_session(engine) as session:
        core.rename_phase(session, phase_id, name)
        session.commit()


def set_phase_parameters(
    phase_id: UUID,
    values: Mapping[PhaseParameter, Timedelta | bool | float | int | str],
    *,
    validate_iccs: bool = False,
    engine: Engine | None = None,
) -> None:
    """Set several parameters of a phase, validated as a group.

    Args:
        phase_id: ID of the phase.
        values: New value for each parameter, keyed by parameter name.
        validate_iccs: If True, verify that an ICCS instance can be built
            with the new values before storing them.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the phase does not exist.
        ValidationError: If any value is invalid. Nothing is changed.
        IccsValidationError: If `validate_iccs` is True and no ICCS instance
            can be built with the new values. Nothing is changed.
    """
    with discard_cached_iccs_on_failure(phase_id), open_session(engine) as session:
        core.set_phase_parameters(
            session, phase_id, values, validate_iccs=validate_iccs
        )
        session.commit()


def toggle_phase_completed(phase_id: UUID, *, engine: Engine | None = None) -> bool:
    """Toggle the `completed` flag of a phase.

    Args:
        phase_id: ID of the phase.
        engine: Engine to use. Defaults to the project engine.

    Returns:
        The new value of the flag.

    Raises:
        NoResultFound: If the phase does not exist.
    """
    with open_session(engine) as session:
        completed = core.toggle_phase_completed(session, phase_id)
        session.commit()
    return completed
