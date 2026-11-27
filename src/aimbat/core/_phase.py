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
    phase_component,
    phase_label,
    undefer_counts,
)
from aimbat.models._parameters import AimbatPhaseParametersBase
from aimbat.types import PhaseParameter
from aimbat.utils import check_field_name_flags, dump_models, rel

__all__ = [
    "AmbiguousPhaseError",
    "PhaseRemovalReport",
    "PhaseRenameReport",
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
    """Raised when the name or component given selects several phases of an event.

    Attributes:
        labels: The phases selected, as `phase_label` shows them, sorted.
        by: What selects one of them: `"name"` or `"component"`.
    """

    def __init__(
        self,
        event_id: UUID,
        labels: Sequence[str],
        by: Literal["name", "component"] = "name",
    ) -> None:
        self.labels = tuple(sorted(labels))
        self.by = by
        super().__init__(
            f"Event {event_id} has phases {', '.join(self.labels)}. Select one "
            + f"by {by}."
        )


def resolve_phase(
    session: Session,
    event_id: UUID,
    name: str | None = None,
    component: str | None = None,
) -> AimbatPhase:
    """Return the phase of an event selected by name and component.

    With both given, the phase of that name on that component. With one,
    the event's only phase of that name, or on that component. With
    neither, the event's only phase.

    Args:
        session: Database session.
        event_id: ID of the event.
        name: Name of the phase.
        component: Component of the phase (`phase_component`).

    Returns:
        The phase.

    Raises:
        NoResultFound: If the event does not exist, or no phase of it
            matches.
        AmbiguousPhaseError: If several phases of the event match.
    """
    if session.get(AimbatEvent, event_id) is None:
        raise NoResultFound(f"No event found with ID {event_id}.")
    phases = session.exec(
        select(AimbatPhase)
        .where(col(AimbatPhase.event_id) == event_id)
        .order_by(col(AimbatPhase.name), col(AimbatPhase.component))
    ).all()
    if not phases:
        raise NoResultFound(f"Event {event_id} has no phases.")
    matching = [
        p
        for p in phases
        if (name is None or p.name == name)
        and (component is None or p.component == component)
    ]
    if not matching:
        wanted = (
            phase_label(name, component)
            if name is not None and component is not None
            else repr(name)
            if name is not None
            else f"on component {component!r}"
        )
        known = ", ".join(phase_label(p.name, p.component) for p in phases)
        raise NoResultFound(
            f"Event {event_id} has no phase {wanted}. Its phases: {known}."
        )
    if len(matching) > 1:
        one_name = len({p.name for p in matching}) == 1
        by: Literal["name", "component"] = "component" if one_name else "name"
        raise AmbiguousPhaseError(
            event_id, [phase_label(p.name, p.component) for p in matching], by
        )
    return matching[0]


def default_phase_parameters(name: str, component: str = "") -> AimbatPhaseParameters:
    """Return new parameters for the phase `name` on `component`.

    The values come from the current settings, the same for every phase.

    Args:
        name: Name of the phase.
        component: Component of the phase (`phase_component`).
    """
    del name, component
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
        The phases, ordered by event time, name and component.
    """
    logger.debug(f"Getting phases ({event_id=}, {name=}).")

    statement = select(AimbatPhase).join(AimbatEvent)
    if event_id is not None:
        statement = statement.where(col(AimbatPhase.event_id) == event_id)
    if name is not None:
        statement = statement.where(col(AimbatPhase.name) == name)
    statement = statement.order_by(
        col(AimbatEvent.time), col(AimbatPhase.name), col(AimbatPhase.component)
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


def _picks_named(session: Session, event_id: UUID, name: str) -> Sequence[AimbatPick]:
    """Picks of an event named `name`: matched to its seismograms, or assigned to it."""
    seismogram_ids = select(AimbatSeismogram.id).where(
        col(AimbatSeismogram.event_id) == event_id
    )
    return session.exec(
        select(AimbatPick)
        .where(col(AimbatPick.phase_name) == name)
        .where(
            or_(
                col(AimbatPick.seismogram_id).in_(seismogram_ids),
                col(AimbatPick.event_id) == event_id,
            )
        )
    ).all()


@dataclass(frozen=True, slots=True)
class PhaseRenameReport:
    """What `rename_phase` renamed."""

    event_id: UUID
    event_time: Timestamp
    old_name: str
    new_name: str
    components: tuple[str, ...]
    """Components of the phases renamed, sorted."""
    picks: int
    """Picks of the event renamed with them."""


def rename_phase(session: Session, phase_id: UUID, name: str) -> PhaseRenameReport:
    """Rename a phase on every component, and the picks of its event named for it.

    Picks carry a phase name but no component, so every phase of the event
    with the old name is renamed.

    Args:
        session: Database session.
        phase_id: ID of one of the phases.
        name: New name.

    Returns:
        The phases and picks renamed.

    Raises:
        NoResultFound: If no phase with the given ID is found.
        ValueError: If the name is not a valid phase name, or the event
            already has a phase of that name on one of the components.
    """
    from ._picks import validate_phase_name

    phase = _phase(session, phase_id)
    name = validate_phase_name(name)
    old_name = phase.name
    renamed = sorted(
        (p for p in phase.event.phases if p.name == old_name),
        key=lambda p: p.component,
    )
    components = tuple(p.component for p in renamed)
    if name == old_name:
        return PhaseRenameReport(
            phase.event_id, phase.event.time, old_name, name, components, 0
        )
    taken = sorted(
        p.component
        for p in phase.event.phases
        if p.name == name and p.component in components
    )
    if taken:
        labels = ", ".join(phase_label(name, c) for c in taken)
        raise ValueError(f"The event already has phase {labels}.")

    logger.info(f"Renaming phase {old_name!r} of event {phase.event_id} to {name!r}.")

    picks = _picks_named(session, phase.event_id, old_name)
    for pick in picks:
        pick.phase_name = name
        session.add(pick)
    for each in renamed:
        each.name = name
        session.add(each)
    session.flush()
    return PhaseRenameReport(
        phase.event_id, phase.event.time, old_name, name, components, len(picks)
    )


@dataclass(frozen=True, slots=True)
class PhaseRemovalReport:
    """What `remove_phase` deleted and dismissed."""

    event_id: UUID
    event_time: Timestamp
    phase_name: str
    component: str
    rows: int
    """Rows of the phase deleted."""
    snapshots: int
    """Snapshots of the phase deleted."""
    dismissed_picks: int
    """Picks named for the phase on the component's seismograms that were dismissed."""
    dismissed_unmatched: int
    """Unmatched picks of the event named for the phase that were dismissed."""
    kept_unmatched: int
    """Unmatched picks named for the phase kept for its other components."""
    other_components: tuple[str, ...]
    """Components on which the event keeps a phase of the name, sorted."""


def remove_phase(session: Session, phase_id: UUID) -> PhaseRemovalReport:
    """Delete a phase, and dismiss the picks of its event named for it on its component.

    The rows, parameters, quality and snapshots of the phase are deleted
    with it. Picks on seismograms of other components are left alone.
    Unmatched picks of the name are dismissed only when no phase of the
    name remains in the event.

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
    others = tuple(
        sorted(
            p.component
            for p in phase.event.phases
            if p.name == phase.name and p.id != phase.id
        )
    )
    dismissed = dismissed_unmatched = kept_unmatched = 0
    for pick in _picks_named(session, phase.event_id, phase.name):
        if pick.dismissed:
            continue
        if pick.seismogram_id is None:
            if others:
                kept_unmatched += 1
                continue
            dismissed_unmatched += 1
        else:
            seismogram = session.get(AimbatSeismogram, pick.seismogram_id)
            if (
                seismogram is None
                or seismogram.event_id != phase.event_id
                or phase_component(seismogram.station) != phase.component
            ):
                continue
            dismissed += 1
        pick.dismissed = True
        session.add(pick)
    report = PhaseRemovalReport(
        event_id=phase.event_id,
        event_time=phase.event.time,
        phase_name=phase.name,
        component=phase.component,
        rows=len(phase.seismogram_parameters),
        snapshots=len(phase.snapshots),
        dismissed_picks=dismissed,
        dismissed_unmatched=dismissed_unmatched,
        kept_unmatched=kept_unmatched,
        other_components=others,
    )
    label = phase_label(phase.name, phase.component)
    logger.info(f"Removing phase {label!r} of event {phase.event_id}.")
    session.delete(phase)
    flush_deletes(session)
    return report


def _with_phase_names(
    data: list[dict[str, Any]],
    phases: Iterable[AimbatPhase],
    *,
    by_alias: bool,
    by_title: bool,
) -> list[dict[str, Any]]:
    """Add the phase name and component to each dumped record, after its phase ID."""
    id_key, name_key, component_key = (
        ("phaseId", "phaseName", "phaseComponent")
        if by_alias
        else ("Phase ID", "Phase", "Component")
        if by_title
        else ("phase_id", "phase_name", "phase_component")
    )
    result = []
    for record, phase in zip(data, phases, strict=True):
        out: dict[str, Any] = {}
        for key, value in record.items():
            out[key] = value
            if key == id_key:
                out[name_key] = phase.name
                out[component_key] = phase.component
        out.setdefault(name_key, phase.name)
        out.setdefault(component_key, phase.component)
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

    Each record carries the name and component of its phase next to the
    phase ID.

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
    return _with_phase_names(data, phases, by_alias=by_alias, by_title=by_title)


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
