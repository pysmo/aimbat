"""Look up, list and rename the phases of an event, and set their parameters."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, overload
from uuid import UUID

from pandas import Timedelta, Timestamp
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, or_, select

from aimbat import settings
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPhaseParameters,
    AimbatPhaseRead,
    AimbatPick,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    SeismogramQualityStats,
    undefer_counts,
)
from aimbat.models._parameters import AimbatPhaseParametersBase
from aimbat.types import PhaseParameter
from aimbat.utils import check_field_name_flags, dump_models, rel

__all__ = [
    "AmbiguousPhaseError",
    "PhaseRemovalReport",
    "default_phase_parameters",
    "dump_phase_parameter_table",
    "dump_phase_quality_table",
    "dump_phase_table",
    "get_completed_phases",
    "get_phase_quality",
    "get_phases",
    "remove_phase",
    "rename_phase",
    "resolve_phase",
    "set_phase_parameter",
    "set_phase_parameters",
    "toggle_phase_completed",
]

type PhaseParameterBool = Literal[
    PhaseParameter.COMPLETED, PhaseParameter.BANDPASS_APPLY
]
type PhaseParameterFloat = Literal[
    PhaseParameter.MIN_CC,
    PhaseParameter.BANDPASS_FMIN,
    PhaseParameter.BANDPASS_FMAX,
    PhaseParameter.RAMP_WIDTH,
    PhaseParameter.MCCC_DAMP,
    PhaseParameter.MCCC_MIN_CC,
]
type PhaseParameterInt = Literal[PhaseParameter.CORNERS]
type PhaseParameterTimedelta = Literal[
    PhaseParameter.WINDOW_PRE, PhaseParameter.WINDOW_POST
]


class AmbiguousPhaseError(ValueError):
    """Raised when a phase is not named and the event has several.

    Attributes:
        names: Names of the event's phases, sorted.
    """

    def __init__(self, event_id: UUID, names: Sequence[str]) -> None:
        self.names = tuple(sorted(names))
        super().__init__(
            f"Event {event_id} has phases {', '.join(self.names)}. Select one "
            + "by name."
        )


def resolve_phase(
    session: Session, event_id: UUID, name: str | None = None
) -> AimbatPhase:
    """Return the named phase of an event, or its only phase when `name` is `None`.

    Args:
        session: Database session.
        event_id: ID of the event.
        name: Name of the phase, or `None` for the event's only phase.

    Returns:
        The phase.

    Raises:
        NoResultFound: If the event does not exist, has no phase of that
            name, or has no phase.
        AmbiguousPhaseError: If `name` is `None` and the event has several
            phases.
    """
    if session.get(AimbatEvent, event_id) is None:
        raise NoResultFound(f"No event found with ID {event_id}.")
    phases = session.exec(
        select(AimbatPhase)
        .where(col(AimbatPhase.event_id) == event_id)
        .order_by(col(AimbatPhase.name))
    ).all()
    if name is not None:
        for phase in phases:
            if phase.name == name:
                return phase
        known = ", ".join(p.name for p in phases) or "none"
        raise NoResultFound(
            f"Event {event_id} has no phase {name!r}. Its phases: {known}."
        )
    if not phases:
        raise NoResultFound(f"Event {event_id} has no phases.")
    if len(phases) > 1:
        raise AmbiguousPhaseError(event_id, [p.name for p in phases])
    return phases[0]


def default_phase_parameters(name: str) -> AimbatPhaseParameters:
    """Return new parameters for a phase called `name`.

    The values come from the current settings, the same for every name.

    Args:
        name: Name of the phase.
    """
    del name
    return AimbatPhaseParameters(
        completed=False,
        ramp_width=settings.ramp_width,
        window_pre=settings.window_pre,
        window_post=settings.window_post,
        bandpass_apply=settings.bandpass_apply,
        bandpass_fmin=settings.bandpass_fmin,
        bandpass_fmax=settings.bandpass_fmax,
        corners=settings.corners,
        min_cc=settings.min_cc,
        mccc_damp=settings.mccc_damp,
        mccc_min_cc=settings.mccc_min_cc,
    )


def _phase(session: Session, phase_id: UUID) -> AimbatPhase:
    """Return the phase with ID `phase_id`.

    Raises:
        NoResultFound: If there is no such phase.
    """
    phase = session.get(AimbatPhase, phase_id)
    if phase is None:
        raise NoResultFound(f"No phase found with ID {phase_id}.")
    return phase


def _phase_loads() -> tuple[Any, ...]:
    """Loader options for a phase's event, parameters, quality and rows."""
    return (
        selectinload(rel(AimbatPhase.event)),
        selectinload(rel(AimbatPhase.parameters)),
        selectinload(rel(AimbatPhase.quality)),
        selectinload(rel(AimbatPhase.seismogram_parameters)).selectinload(
            rel(AimbatSeismogramParameters.quality)
        ),
    )


def get_phases(
    session: Session,
    event_id: UUID | None = None,
    name: str | None = None,
    *,
    with_counts: bool = False,
) -> Sequence[AimbatPhase]:
    """Get the phases of one event or of every event, optionally by name.

    Args:
        session: Database session.
        event_id: Event whose phases are returned. Every event's if `None`.
        name: Only phases of this name, across the events covered.
        with_counts: Whether to load the deferred counts in the same query.

    Returns:
        The phases, ordered by event time and name.
    """
    logger.debug(f"Getting phases ({event_id=}, {name=}).")

    statement = select(AimbatPhase).join(AimbatEvent)
    if event_id is not None:
        statement = statement.where(col(AimbatPhase.event_id) == event_id)
    if name is not None:
        statement = statement.where(col(AimbatPhase.name) == name)
    statement = statement.order_by(
        col(AimbatEvent.time), col(AimbatPhase.name)
    ).options(*_phase_loads(), *(undefer_counts(AimbatPhase) if with_counts else ()))
    return session.exec(statement).all()


def get_completed_phases(session: Session) -> Sequence[AimbatPhase]:
    """Get the phases marked as completed.

    Args:
        session: Database session.

    Returns:
        Every phase whose `completed` parameter is set.
    """
    logger.debug("Getting completed phases from project.")

    return session.exec(
        select(AimbatPhase)
        .join(AimbatPhaseParameters)
        .where(col(AimbatPhaseParameters.completed).is_(True))
    ).all()


def get_phase_quality(session: Session, phase_id: UUID) -> SeismogramQualityStats:
    """Get aggregated quality statistics for a phase.

    Args:
        session: Database session.
        phase_id: ID of the phase.

    Returns:
        Aggregated seismogram quality statistics. `mccc_rmse` is taken from
        the phase quality record, and is `None` while there are no valid
        MCCC results.

    Raises:
        NoResultFound: If no phase with the given ID is found.
    """
    from ._validity import Validity

    logger.debug(f"Getting quality stats for phase {phase_id}.")

    phase = session.exec(
        select(AimbatPhase)
        .where(col(AimbatPhase.id) == phase_id)
        .options(*_phase_loads())
    ).one_or_none()
    if phase is None:
        raise NoResultFound(f"No phase found with ID {phase_id}.")

    return SeismogramQualityStats.from_phase(phase, Validity.read(session, phase_id))


def _picks_named(session: Session, phase: AimbatPhase) -> Sequence[AimbatPick]:
    """Picks of the phase's event named for the phase."""
    seismogram_ids = select(AimbatSeismogram.id).where(
        col(AimbatSeismogram.event_id) == phase.event_id
    )
    return session.exec(
        select(AimbatPick)
        .where(col(AimbatPick.phase_name) == phase.name)
        .where(
            or_(
                col(AimbatPick.seismogram_id).in_(seismogram_ids),
                col(AimbatPick.event_id) == phase.event_id,
            )
        )
    ).all()


def rename_phase(session: Session, phase_id: UUID, name: str) -> None:
    """Rename a phase, and the picks of its event named for it.

    Args:
        session: Database session.
        phase_id: ID of the phase.
        name: New name.

    Raises:
        NoResultFound: If no phase with the given ID is found.
        ValueError: If the name is not a valid phase name, or another phase
            of the event already has it.
    """
    from ._picks import validate_phase_name

    phase = _phase(session, phase_id)
    name = validate_phase_name(name)
    if name == phase.name:
        return
    if any(other.name == name for other in phase.event.phases):
        raise ValueError(f"The event already has a phase {name!r}.")

    logger.info(f"Renaming phase {phase.name!r} of event {phase.event_id} to {name!r}.")

    for pick in _picks_named(session, phase):
        pick.phase_name = name
        session.add(pick)
    phase.name = name
    session.add(phase)
    session.flush()


@dataclass(frozen=True, slots=True)
class PhaseRemovalReport:
    """What `remove_phase` deleted and dismissed."""

    event_id: UUID
    event_time: Timestamp
    phase_name: str
    rows: int
    """Rows of the phase deleted."""
    snapshots: int
    """Snapshots of the phase deleted."""
    dismissed_picks: int
    """Picks of the event named for the phase that were dismissed."""


def remove_phase(session: Session, phase_id: UUID) -> PhaseRemovalReport:
    """Delete a phase, and dismiss the picks of its event named for it.

    The rows, parameters, quality and snapshots of the phase are deleted
    with it.

    Args:
        session: Database session.
        phase_id: ID of the phase.

    Returns:
        What was deleted and dismissed.

    Raises:
        NoResultFound: If no phase with the given ID is found.
    """
    from ._session import flush_deletes

    phase = _phase(session, phase_id)
    dismissed = 0
    for pick in _picks_named(session, phase):
        if not pick.dismissed:
            pick.dismissed = True
            session.add(pick)
            dismissed += 1
    report = PhaseRemovalReport(
        event_id=phase.event_id,
        event_time=phase.event.time,
        phase_name=phase.name,
        rows=len(phase.seismogram_parameters),
        snapshots=len(phase.snapshots),
        dismissed_picks=dismissed,
    )
    logger.info(f"Removing phase {phase.name!r} of event {phase.event_id}.")
    session.delete(phase)
    flush_deletes(session)
    return report


def _with_phase_names(
    data: list[dict[str, Any]],
    names: Iterable[str],
    *,
    by_alias: bool,
    by_title: bool,
) -> list[dict[str, Any]]:
    """Add the phase name to each dumped record, after its phase ID."""
    id_key, name_key = (
        ("phaseId", "phaseName")
        if by_alias
        else ("Phase ID", "Phase")
        if by_title
        else ("phase_id", "phase_name")
    )
    result = []
    for record, name in zip(data, names, strict=True):
        out: dict[str, Any] = {}
        for key, value in record.items():
            out[key] = value
            if key == id_key:
                out[name_key] = name
        out.setdefault(name_key, name)
        result.append(out)
    return result


def dump_phase_table(
    session: Session,
    from_read_model: bool = False,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
    name: str | None = None,
) -> list[dict[str, Any]]:
    """Dump the phases to a JSON-serialisable list of dicts.

    Args:
        session: Database session.
        from_read_model: Whether to dump from the read model (True) or the ORM model.
        by_alias: Whether to use serialisation aliases for the field names.
        by_title: Whether to use the field title metadata for the field names
            (only applicable when from_read_model is True). Mutually exclusive
            with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event whose phases are dumped. Every event's if `None`.
        name: Only phases of this name, across the events covered.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
        ValueError: If `by_title` is True but `from_read_model` is False.
    """
    from ._validity import Validity

    logger.debug("Dumping AIMBAT phase table to json.")

    check_field_name_flags(by_alias, by_title, from_read_model)

    phases = get_phases(session, event_id, name, with_counts=from_read_model)
    if not from_read_model:
        return dump_models(phases, AimbatPhase, by_alias=by_alias, exclude=exclude)

    validity = Validity.read(session, event_id=event_id)
    reads = [AimbatPhaseRead.from_phase(p, validity, session=session) for p in phases]
    return dump_models(
        reads, AimbatPhaseRead, by_alias=by_alias, by_title=by_title, exclude=exclude
    )


def dump_phase_parameter_table(
    session: Session,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
    name: str | None = None,
) -> list[dict[str, Any]]:
    """Dump the phase parameters to a JSON-serialisable list of dicts.

    Each record carries the name of its phase next to the phase ID.

    Args:
        session: Database session.
        by_alias: Whether to use serialisation aliases for the field names.
        by_title: Whether to use the field title metadata for the field names.
            Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event whose phases are dumped. Every event's if `None`.
        name: Only phases of this name, across the events covered.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """
    logger.debug("Dumping AIMBAT phase parameter table to json.")

    check_field_name_flags(by_alias, by_title)

    phases = get_phases(session, event_id, name)
    data = dump_models(
        [p.parameters for p in phases],
        AimbatPhaseParameters,
        by_alias=by_alias,
        by_title=by_title,
        exclude=exclude,
    )
    return _with_phase_names(
        data, (p.name for p in phases), by_alias=by_alias, by_title=by_title
    )


def dump_phase_quality_table(
    session: Session,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
    name: str | None = None,
) -> list[dict[str, Any]]:
    """Dump aggregated quality statistics per phase to json.

    Args:
        session: Database session.
        by_alias: Whether to use serialisation aliases for the field names.
        by_title: Whether to use the field title metadata for the field names.
            Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event whose phases are dumped. Every event's if `None`.
        name: Only phases of this name, across the events covered.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """
    from ._validity import Validity

    logger.debug("Dumping AIMBAT phase quality table to json.")

    check_field_name_flags(by_alias, by_title)

    phases = get_phases(session, event_id, name)
    validity = Validity.read(session, event_id=event_id)
    stats = [SeismogramQualityStats.from_phase(p, validity) for p in phases]

    return dump_models(
        stats,
        SeismogramQualityStats,
        by_alias=by_alias,
        by_title=by_title,
        exclude=(exclude or set()) | {"station_id", "snapshot_id"},
    )


def toggle_phase_completed(session: Session, phase_id: UUID) -> bool:
    """Flip the `completed` flag on the parameters of a phase.

    `completed` is bookkeeping and an input to no result, so this does not
    go through `set_phase_parameters`' restore from snapshots.

    Args:
        session: Database session.
        phase_id: ID of the phase.

    Returns:
        The new value of the `completed` flag.

    Raises:
        NoResultFound: If no phase with the given ID is found.
    """
    logger.debug(f"Toggling completed flag for phase {phase_id}.")

    parameters = _phase(session, phase_id).parameters
    parameters.completed = not parameters.completed
    session.add(parameters)
    session.flush()
    return parameters.completed


@overload
def set_phase_parameter(
    session: Session,
    phase_id: UUID,
    name: PhaseParameterTimedelta,
    value: Timedelta,
    *,
    validate_iccs: bool = ...,
) -> None: ...


@overload
def set_phase_parameter(
    session: Session,
    phase_id: UUID,
    name: PhaseParameterFloat,
    value: float,
    *,
    validate_iccs: bool = ...,
) -> None: ...


@overload
def set_phase_parameter(
    session: Session,
    phase_id: UUID,
    name: PhaseParameterInt,
    value: int,
    *,
    validate_iccs: bool = ...,
) -> None: ...


@overload
def set_phase_parameter(
    session: Session,
    phase_id: UUID,
    name: PhaseParameterBool,
    value: bool | str,
    *,
    validate_iccs: bool = ...,
) -> None: ...


@overload
def set_phase_parameter(
    session: Session,
    phase_id: UUID,
    name: PhaseParameter,
    value: Timedelta | bool | float | int | str,
    *,
    validate_iccs: bool = ...,
) -> None: ...


def set_phase_parameter(
    session: Session,
    phase_id: UUID,
    name: PhaseParameter,
    value: Timedelta | bool | float | int | str,
    *,
    validate_iccs: bool = False,
) -> None:
    """Set a parameter of a phase.

    Args:
        session: Database session.
        phase_id: ID of the phase.
        name: Name of the parameter.
        value: Value to set.
        validate_iccs: If True, attempt ICCS construction with the new value
            before storing it. Raises and leaves the session unchanged on failure.

    Raises:
        NoResultFound: If no phase with the given ID is found.
        ValidationError: If `value` fails Pydantic validation for `name`.
        IccsValidationError: If `validate_iccs` is True and ICCS construction
            is rejected by the new value.
    """
    set_phase_parameters(session, phase_id, {name: value}, validate_iccs=validate_iccs)


def set_phase_parameters(
    session: Session,
    phase_id: UUID,
    values: Mapping[PhaseParameter, Timedelta | bool | float | int | str],
    *,
    validate_iccs: bool = False,
) -> None:
    """Set several parameters of a phase at once, validated as a group.

    The whole update is validated against the merged parameter state, so a
    combination of values that no single-field order could reach (e.g. a new
    `bandpass_fmin` above the old `bandpass_fmax` alongside the new
    `bandpass_fmax`) is accepted.

    Args:
        session: Database session.
        phase_id: ID of the phase.
        values: Parameter name -> new value. An empty mapping is a no-op.
        validate_iccs: If True, attempt ICCS construction with the new values
            before storing them. Raises and leaves the session unchanged on failure.

    Raises:
        NoResultFound: If no phase with the given ID is found.
        ValidationError: If any value fails Pydantic validation.
        IccsValidationError: If `validate_iccs` is True and ICCS construction
            is rejected by the new values.
    """
    from ._iccs import validate_iccs_construction
    from ._snapshot import resync_quality

    updates = {str(name): value for name, value in values.items()}
    logger.debug(f"Setting {updates} for phase {phase_id}.")

    phase = _phase(session, phase_id)
    if not updates:
        return

    parameters = AimbatPhaseParametersBase.model_validate(
        phase.parameters,
        update=updates,
    )

    if validate_iccs:
        validate_iccs_construction(phase, parameters=parameters)

    for name in updates:
        setattr(phase.parameters, name, getattr(parameters, name))
    session.add(phase.parameters)
    resync_quality(session, phase_id)
