"""Check whether the phases of a project are ready for processing.

Readiness is derived from the stored picks, seismograms and phases each time
it is checked, and is never stored. Each problem found is a
`ReadinessItem`, which names the command that fixes it. Blocking items
prevent processing of the phases they cover. Notices are listed and do not
block.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from uuid import UUID

from pandas import Timestamp
from sqlmodel import Session, col, or_, select

from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPick,
    AimbatSeismogram,
)
from aimbat.utils.formatters import fmt_timestamp

from ._picks import (
    PickState,
    _candidates,
    _has_natural_key,
    _stored_target,
    pick_states,
    validate_pick,
)

__all__ = [
    "NotReadyError",
    "ReadinessItem",
    "ReadinessKind",
    "ReadinessSeverity",
    "readiness",
    "require_ready",
]


class ReadinessSeverity(StrEnum):
    """Whether a readiness item prevents processing."""

    BLOCKING = auto()
    """Processing of the phases the item covers is refused."""

    NOTICE = auto()
    """Listed, but processing is not refused."""


class ReadinessKind(StrEnum):
    """The problem a readiness item describes."""

    UNNAMED_PICK = auto()
    """Picks of the event without a phase name."""

    UNMATCHED_PICK = auto()
    """Named picks of the event that match no seismogram."""

    AMBIGUOUS_PICK = auto()
    """Picks of the event that match several seismograms."""

    EMPTY_PHASE = auto()
    """A phase without initial picks."""

    UNPROMOTED_PICKS = auto()
    """Named, matched picks that are not initial picks of a seismogram."""

    CONFLICTING_PICK = auto()
    """Picks whose seismogram already has another initial pick for the phase."""

    UNRESOLVED_EVENT = auto()
    """Picks whose event is not in the project."""

    SEISMOGRAM_WITHOUT_PICKS = auto()
    """Seismograms of the event without an initial pick in any phase."""

    PICK_AFTER_END = auto()
    """Initial picks after the end of their seismogram."""


@dataclass(frozen=True, slots=True)
class ReadinessItem:
    """One problem found by `readiness`, with the commands that fix it.

    An item belongs to an event and a phase. An item without an event
    belongs to the project. An item of an event without a phase name covers
    every phase of the event. An item with a phase name and no phase ID
    names a phase the event does not have.
    """

    kind: ReadinessKind
    severity: ReadinessSeverity
    event_id: UUID | None
    phase_id: UUID | None
    phase_name: str | None
    pick_ids: tuple[UUID, ...] = ()
    seismogram_ids: tuple[UUID, ...] = ()
    message: str = ""
    fixes: tuple[str, ...] = ()
    """Commands that fix the problem, with full IDs. Upper-case words are
    placeholders."""

    @property
    def blocking(self) -> bool:
        """Whether the item prevents processing."""
        return self.severity is ReadinessSeverity.BLOCKING

    @property
    def count(self) -> int:
        """Number of picks, seismograms or phases the item describes."""
        return len(self.pick_ids) or len(self.seismogram_ids) or 1

    def covers(self, phase: AimbatPhase) -> bool:
        """Whether the item applies to `phase`."""
        if self.event_id != phase.event_id:
            return False
        if self.phase_id is not None:
            return self.phase_id == phase.id
        return self.phase_name is None


class NotReadyError(ValueError):
    """Raised by `require_ready` when blocking items apply to a phase."""

    def __init__(
        self, phase: AimbatPhase, event: AimbatEvent, items: Sequence[ReadinessItem]
    ) -> None:
        self.items = tuple(items)
        lines = [
            f"Phase {phase.name} of event {fmt_timestamp(event.time)} is not "
            + f"ready for processing ({_count(len(self.items), 'blocking item')}):"
        ]
        for item in self.items:
            lines.append(f"- {item.message}")
            lines.extend(f"  Fix: {fix}" for fix in item.fixes)
        lines.append("Run `aimbat data check` for every item of the project.")
        super().__init__("\n".join(lines))


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _one_or(ids: Sequence[UUID], placeholder: str) -> str:
    """The ID if there is exactly one, else the placeholder."""
    return str(ids[0]) if len(ids) == 1 else placeholder


def _unmatched_reason(
    session: Session, pick: AimbatPick, event: AimbatEvent
) -> str | None:
    """Why the only candidate of an unmatched pick was refused, if it was."""
    if not _has_natural_key(pick):
        return None
    try:
        candidates = _candidates(session, _stored_target(pick), event, None)
    except ValueError as exc:
        return str(exc)
    if len(candidates) != 1:
        return None
    return " ".join(validate_pick(session, pick, candidates[0]).errors) or None


def _by_phase_name(picks: Iterable[AimbatPick]) -> dict[str | None, list[AimbatPick]]:
    grouped: dict[str | None, list[AimbatPick]] = defaultdict(list)
    for pick in picks:
        grouped[pick.phase_name].append(pick)
    return dict(sorted(grouped.items(), key=lambda kv: kv[0] or ""))


def _event_picks(session: Session, event_id: UUID) -> list[AimbatPick]:
    """Undismissed picks matched to the event's seismograms or assigned to it."""
    statement = (
        select(AimbatPick)
        .outerjoin(
            AimbatSeismogram,
            col(AimbatSeismogram.id) == col(AimbatPick.seismogram_id),
        )
        .where(
            col(AimbatPick.dismissed).is_(False),
            or_(
                col(AimbatSeismogram.event_id) == event_id,
                col(AimbatPick.event_id) == event_id,
            ),
        )
        .order_by(col(AimbatPick.time), col(AimbatPick.id))
    )
    return list(session.exec(statement).all())


def _pick_items(
    session: Session, event: AimbatEvent, phases: dict[str, AimbatPhase]
) -> list[ReadinessItem]:
    """Items R1, R2, R3, R5 and R6 of an event."""
    picks = _event_picks(session, event.id)
    states = pick_states(session, pick_ids=[p.id for p in picks])
    items: list[ReadinessItem] = []

    def item(
        kind: ReadinessKind,
        blocking: bool,
        name: str | None,
        group: Sequence[AimbatPick],
        message: str,
        fixes: Iterable[str],
    ) -> None:
        phase = phases.get(name) if name is not None else None
        items.append(
            ReadinessItem(
                kind=kind,
                severity=(
                    ReadinessSeverity.BLOCKING if blocking else ReadinessSeverity.NOTICE
                ),
                event_id=event.id,
                phase_id=phase.id if phase else None,
                phase_name=name,
                pick_ids=tuple(p.id for p in group),
                message=message,
                fixes=tuple(fixes),
            )
        )

    unnamed = [p for p in picks if p.phase_name is None]
    if unnamed:
        item(
            ReadinessKind.UNNAMED_PICK,
            True,
            None,
            unnamed,
            f"{_count(len(unnamed), 'pick')} without a phase name. Such a pick "
            + "may belong to any phase of the event.",
            (
                f"aimbat pick name PHASE --event {event.id} --unnamed",
                f"aimbat pick remove --event {event.id} --unnamed",
            ),
        )

    def of_state(state: PickState) -> dict[str | None, list[AimbatPick]]:
        return _by_phase_name(p for p in picks if states.get(p.id) is state)

    for name, group in of_state(PickState.UNMATCHED).items():
        if name is None:
            continue
        ids = [p.id for p in group]
        reasons = [
            f"Pick {p.id}: {reason}"
            for p in group
            if (reason := _unmatched_reason(session, p, event)) is not None
        ]
        item(
            ReadinessKind.UNMATCHED_PICK,
            name in phases,
            name,
            group,
            " ".join(
                [
                    f"{_count(len(group), 'pick')} of phase {name} matching no "
                    + "seismogram of the event.",
                    *reasons,
                ]
            ),
            (
                f"aimbat pick match {_one_or(ids, 'PICK')} SEISMOGRAM",
                f"aimbat pick remove {_one_or(ids, 'PICK')}",
            ),
        )

    for name, group in of_state(PickState.AMBIGUOUS).items():
        ids = [p.id for p in group]
        of_phase = f" of phase {name}" if name is not None else ""
        item(
            ReadinessKind.AMBIGUOUS_PICK,
            name is None or name in phases,
            name,
            group,
            f"{_count(len(group), 'pick')}{of_phase} matching several "
            + "seismograms of the event.",
            (f"aimbat pick match {_one_or(ids, 'PICK')} SEISMOGRAM",),
        )

    for name, group in of_state(PickState.UNPROMOTED).items():
        assert name is not None
        item(
            ReadinessKind.UNPROMOTED_PICKS,
            False,
            name,
            group,
            f"{_count(len(group), 'matched pick')} of phase {name} not promoted "
            + "to initial picks.",
            (f"aimbat pick promote --event {event.id} --phase {name}",),
        )

    for name, group in of_state(PickState.CONFLICT).items():
        assert name is not None
        ids = [p.id for p in group]
        item(
            ReadinessKind.CONFLICTING_PICK,
            False,
            name,
            group,
            f"{_count(len(group), 'pick')} of phase {name} differing from the "
            + "initial pick their seismogram already has.",
            (
                f"aimbat pick promote --pick {_one_or(ids, 'PICK')} --replace",
                f"aimbat pick remove {_one_or(ids, 'PICK')}",
            ),
        )

    return items


def _phase_items(
    phases: Iterable[AimbatPhase], end_times: dict[UUID, Timestamp] | None
) -> list[ReadinessItem]:
    """Items R4 and R9 of the given phases."""
    items: list[ReadinessItem] = []
    for phase in phases:
        rows = phase.seismogram_parameters
        if not rows:
            items.append(
                ReadinessItem(
                    kind=ReadinessKind.EMPTY_PHASE,
                    severity=ReadinessSeverity.BLOCKING,
                    event_id=phase.event_id,
                    phase_id=phase.id,
                    phase_name=phase.name,
                    message=f"Phase {phase.name} without initial picks.",
                    fixes=(
                        f"aimbat pick set SEISMOGRAM {phase.name} TIME",
                        f"aimbat phase remove --event {phase.event_id} "
                        + f"--phase {phase.name}",
                    ),
                )
            )
            continue
        if end_times is None:
            continue

        late = []
        for row in rows:
            seismogram = row.seismogram
            if seismogram.id not in end_times:
                end_times[seismogram.id] = seismogram.end_time
            if row.pick.time > end_times[seismogram.id]:
                late.append(row)
        if late:
            late.sort(key=lambda r: (r.pick.time, r.pick_id))
            pick_ids = [r.pick_id for r in late]
            seismogram_ids = [r.seismogram_id for r in late]
            items.append(
                ReadinessItem(
                    kind=ReadinessKind.PICK_AFTER_END,
                    severity=ReadinessSeverity.BLOCKING,
                    event_id=phase.event_id,
                    phase_id=phase.id,
                    phase_name=phase.name,
                    pick_ids=tuple(pick_ids),
                    seismogram_ids=tuple(seismogram_ids),
                    message=f"{_count(len(late), 'initial pick')} of phase "
                    + f"{phase.name} after the end of their seismogram.",
                    fixes=(
                        f"aimbat pick set {_one_or(seismogram_ids, 'SEISMOGRAM')} "
                        + f"{phase.name} TIME --replace",
                        f"aimbat pick remove {_one_or(pick_ids, 'PICK')}",
                    ),
                )
            )
    return items


def _seismogram_item(event: AimbatEvent) -> list[ReadinessItem]:
    """Item R8 of an event."""
    bare = sorted(
        (s for s in event.seismograms if not s.phase_rows), key=lambda s: str(s.id)
    )
    if not bare:
        return []
    ids = [s.id for s in bare]
    return [
        ReadinessItem(
            kind=ReadinessKind.SEISMOGRAM_WITHOUT_PICKS,
            severity=ReadinessSeverity.NOTICE,
            event_id=event.id,
            phase_id=None,
            phase_name=None,
            seismogram_ids=tuple(ids),
            message=f"{_count(len(bare), 'seismogram')} without an initial pick "
            + "in any phase.",
            fixes=(f"aimbat pick set {_one_or(ids, 'SEISMOGRAM')} PHASE TIME",),
        )
    ]


def _project_items(session: Session) -> list[ReadinessItem]:
    """Item R7."""
    picks = session.exec(
        select(AimbatPick)
        .where(
            col(AimbatPick.dismissed).is_(False),
            col(AimbatPick.seismogram_id).is_(None),
            col(AimbatPick.event_id).is_(None),
        )
        .order_by(col(AimbatPick.time), col(AimbatPick.id))
    ).all()
    if not picks:
        return []
    ids = [p.id for p in picks]
    return [
        ReadinessItem(
            kind=ReadinessKind.UNRESOLVED_EVENT,
            severity=ReadinessSeverity.NOTICE,
            event_id=None,
            phase_id=None,
            phase_name=None,
            pick_ids=tuple(ids),
            message=f"{_count(len(picks), 'pick')} whose event is not in the "
            + "project. Matching is retried once the event is added.",
            fixes=(
                "aimbat pick match --retry",
                f"aimbat pick remove {_one_or(ids, 'PICK')}",
            ),
        )
    ]


def readiness(
    session: Session,
    *,
    event_id: UUID | None = None,
    phase_id: UUID | None = None,
    read_data: bool = True,
) -> list[ReadinessItem]:
    """Find what prevents or may affect the processing of phases.

    Items are derived from the stored data, one for each kind of problem,
    event and phase. Dismissed picks are ignored. Checking an initial pick
    against the end of its seismogram reads the seismogram's data.

    Args:
        session: Database session.
        event_id: Only the items of this event. Items of the project are
            left out.
        phase_id: Only the items that cover this phase. Items of the
            project are left out.
        read_data: Whether to check initial picks against the end of their
            seismogram, which reads the seismogram's data.

    Returns:
        The items, by event time, then in the order of `ReadinessKind`.

    Raises:
        NoResultFound: If the event or phase does not exist.
        ValueError: If the phase does not belong to the event.
    """
    phase: AimbatPhase | None = None
    if phase_id is not None:
        phase = session.get_one(AimbatPhase, phase_id)
        if event_id is not None and event_id != phase.event_id:
            raise ValueError(f"Phase {phase_id} does not belong to event {event_id}.")
        event_id = phase.event_id

    if event_id is not None:
        events = [session.get_one(AimbatEvent, event_id)]
    else:
        events = list(
            session.exec(select(AimbatEvent).order_by(col(AimbatEvent.time))).all()
        )

    order = list(ReadinessKind)
    end_times: dict[UUID, Timestamp] | None = {} if read_data else None
    items: list[ReadinessItem] = []
    for event in events:
        phases = {p.name: p for p in sorted(event.phases, key=lambda p: p.name)}
        checked = [phase] if phase is not None else list(phases.values())
        event_items = (
            _pick_items(session, event, phases)
            + _phase_items(checked, end_times)
            + _seismogram_item(event)
        )
        event_items.sort(key=lambda i: order.index(i.kind))
        items.extend(event_items)
    if event_id is None:
        items.extend(_project_items(session))

    if phase is not None:
        items = [i for i in items if i.covers(phase)]
    return items


def require_ready(session: Session, phase_id: UUID) -> None:
    """Check that no blocking item applies to a phase.

    Args:
        session: Database session.
        phase_id: ID of the phase.

    Raises:
        NoResultFound: If the phase does not exist.
        NotReadyError: If blocking items apply to the phase.
    """
    blocking = [i for i in readiness(session, phase_id=phase_id) if i.blocking]
    if blocking:
        phase = session.get_one(AimbatPhase, phase_id)
        raise NotReadyError(phase, phase.event, blocking)
