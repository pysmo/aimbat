"""Actions that modify phases."""

from collections.abc import Callable, Mapping, Sequence
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
    "remove_phases",
    "rename_phase",
    "set_phase_parameters",
    "toggle_phase_completed",
]


@dataclass(frozen=True)
class RemovePhaseResult:
    """What `remove_phase` deleted, or would delete when shown to `confirm`."""

    phase_id: UUID
    event_id: UUID
    event_time: Timestamp
    phase_name: str
    component: str
    rows: int
    """Rows of the phase."""
    snapshots: int
    """Snapshots of the phase."""
    dismissed_picks: int
    """Picks named for the phase on the component's seismograms that are dismissed."""
    dismissed_unmatched: int
    """Unmatched picks of the event named for the phase that are dismissed."""
    kept_unmatched: int
    """Unmatched picks named for the phase kept for its other components."""
    other_components: tuple[str, ...]
    """Components on which the event keeps a phase of the name."""
    removed: bool
    """Whether the phase was deleted."""


def remove_phase(
    phase_id: UUID,
    *,
    confirm: Callable[[RemovePhaseResult], bool] | None = None,
    engine: Engine | None = None,
) -> RemovePhaseResult:
    """Delete a phase, and dismiss the picks of its event named for it on its component.

    The rows, parameters, quality and snapshots of the phase are deleted
    with it. Unmatched picks of the name are dismissed only when no phase of
    the name remains in the event. The dismissed picks are kept, and
    `restore_picks` undoes the dismissal.

    Args:
        phase_id: ID of the phase.
        confirm: Callback that receives the pending deletion before it is
            saved. Deletion proceeds only if it returns True.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the phase does not exist.
    """
    (result,) = remove_phases(
        [phase_id],
        confirm=None if confirm is None else lambda results: confirm(results[0]),
        engine=engine,
    )
    return result


def remove_phases(
    phase_ids: Sequence[UUID],
    *,
    confirm: Callable[[list[RemovePhaseResult]], bool] | None = None,
    engine: Engine | None = None,
) -> list[RemovePhaseResult]:
    """Delete phases together, as `remove_phase` deletes one.

    All phases are saved together, or none.

    Args:
        phase_ids: IDs of the phases.
        confirm: Callback that receives the pending deletions before they
            are saved. Deletion proceeds only if it returns True.
        engine: Engine to use. Defaults to the project engine.

    Returns:
        What was deleted in each phase, in the order given.

    Raises:
        NoResultFound: If a phase does not exist. Nothing is changed.
    """
    ids = list(dict.fromkeys(phase_ids))
    with open_session(engine) as session:
        results = []
        for phase_id in ids:
            report = core.remove_phase(session, phase_id)
            results.append(
                RemovePhaseResult(
                    phase_id=phase_id,
                    event_id=report.event_id,
                    event_time=report.event_time,
                    phase_name=report.phase_name,
                    component=report.component,
                    rows=report.rows,
                    snapshots=report.snapshots,
                    dismissed_picks=report.dismissed_picks,
                    dismissed_unmatched=report.dismissed_unmatched,
                    kept_unmatched=report.kept_unmatched,
                    other_components=report.other_components,
                    removed=False,
                )
            )
        if confirm is not None and not confirm(results):
            session.rollback()
            return results
        session.commit()
    for phase_id in ids:
        core.evict_iccs_cache_entry(phase_id)
    return [replace(result, removed=True) for result in results]


def rename_phase(
    phase_id: UUID, name: str, *, engine: Engine | None = None
) -> core.PhaseRenameReport:
    """Rename a phase on every component, and the picks of its event named for it.

    Args:
        phase_id: ID of one of the phases.
        name: New name.
        engine: Engine to use. Defaults to the project engine.

    Returns:
        The phases and picks renamed.

    Raises:
        NoResultFound: If the phase does not exist.
        ValueError: If the name is not a valid phase name, or the event
            already has a phase of that name on one of the components.
            Nothing is changed.
    """
    with open_session(engine) as session:
        report = core.rename_phase(session, phase_id, name)
        session.commit()
    return report


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
