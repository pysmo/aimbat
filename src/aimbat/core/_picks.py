"""Store, match and promote initial picks.

Picks arrive from `aimbat.io` as `SourcePick` objects. They are named,
matched to seismograms and written as raw `AimbatPick` records. A pick that
is named and matched is promoted: it becomes the initial pick of its
seismogram for the phase of that name, as an `AimbatSeismogramParameters`
row referencing it.

Invariants kept by the functions here: the pick of a row is matched to the
row's seismogram, is not dismissed, has the phase's name, and the phase's
event is the seismogram's event.
"""

import re
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum, auto
from uuid import UUID

from pandas import Timedelta, Timestamp
from sqlmodel import Session, col, or_, select

from pysmo.tools.traveltime import is_standard_phase

from aimbat import settings
from aimbat.io import (
    DataType,
    PickTarget,
    SeismogramTarget,
    SourcePick,
    StationEventTarget,
)
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPick,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
    PickOrigin,
    phase_component,
)
from aimbat.utils.formatters import fmt_timedelta

from ._phase import default_phase_parameters

__all__ = [
    "MAX_PHASE_NAME_LENGTH",
    "MatchResult",
    "MatchStatus",
    "PickChange",
    "PickCheck",
    "PickNaming",
    "PickState",
    "PromotionReport",
    "StoreReport",
    "find_event",
    "match_target",
    "pick_states",
    "promote_picks",
    "rematch_picks",
    "store_picks",
    "validate_phase_name",
    "validate_pick",
]

MAX_PHASE_NAME_LENGTH = 32
"""Longest phase name allowed, in characters."""

_BLANK_OR_CONTROL = re.compile(r"[\s\x00-\x1f\x7f]")


def validate_phase_name(name: str) -> str:
    """Return a phase name stripped of surrounding blanks.

    Args:
        name: Phase name to check.

    Raises:
        ValueError: If the name is empty, contains whitespace or control
            characters, or is longer than `MAX_PHASE_NAME_LENGTH`.
    """
    stripped = name.strip()
    if not stripped:
        raise ValueError("A phase name must not be empty.")
    if _BLANK_OR_CONTROL.search(stripped):
        raise ValueError(
            f"Phase name {stripped!r} contains whitespace or control characters."
        )
    if len(stripped) > MAX_PHASE_NAME_LENGTH:
        raise ValueError(
            f"Phase name {stripped!r} is longer than {MAX_PHASE_NAME_LENGTH} "
            + "characters."
        )
    return stripped


@dataclass(frozen=True, slots=True)
class PickNaming:
    """How ingestion names picks.

    A pick takes its label as name if the label is a valid phase name. A pick
    without a label takes `unlabelled_as`, if given. A pick whose label is
    not a valid phase name stays unnamed.
    """

    unlabelled_as: str | None = None
    """Name for every pick that has no label."""

    skip_unnamed: bool = False
    """Do not store picks that are still unnamed. They are counted instead."""

    def __post_init__(self) -> None:
        if self.unlabelled_as is not None:
            object.__setattr__(
                self, "unlabelled_as", validate_phase_name(self.unlabelled_as)
            )

    def name_for(self, pick: SourcePick) -> str | None:
        """Return the phase name for `pick`, or `None` if it stays unnamed."""
        if pick.label is None:
            return self.unlabelled_as
        try:
            return validate_phase_name(pick.label)
        except ValueError:
            return None


# ----------------------------------------------------------------------------
# Event lookup, shared with `core/_data.py`
# ----------------------------------------------------------------------------


def _format_gap_prefix(
    label: str, time: Timestamp, existing_event: AimbatEvent, gap: Timedelta
) -> str:
    """Build the shared origin-time/gap/existing-event sentence fragment."""
    return (
        f"{label} has origin time {time}, {fmt_timedelta(gap)} from "
        + f"existing event {existing_event.id} ({existing_event.time})"
    )


def _format_reused_near_duplicate_message(
    label: str,
    time: Timestamp,
    existing_event: AimbatEvent,
    gap: Timedelta,
    tolerance: Timedelta,
) -> str:
    """Build the noise-band near-duplicate-event reuse message."""
    prefix = _format_gap_prefix(label, time, existing_event, gap)
    return (
        f"Near-duplicate event: {prefix}, within the configured "
        + f"duplicate-detection tolerance ({fmt_timedelta(tolerance)}) but not "
        + "an exact match. Reusing the existing event; its stored time and "
        + "location are kept unchanged. Set 'event_duplicate_strict' to treat "
        + "close origin times as genuinely distinct events instead."
    )


def _format_ambiguous_gap_message(
    label: str,
    time: Timestamp,
    existing_event: AimbatEvent,
    gap: Timedelta,
    tolerance: Timedelta,
    raise_tolerance: Timedelta,
) -> str:
    """Build the ambiguous-gap-band event-time-conflict message."""
    prefix = _format_gap_prefix(label, time, existing_event, gap)
    return (
        f"Event time conflict: {prefix}, too large a gap to be explained by "
        + "ordinary timestamp precision noise (tolerance "
        + f"{fmt_timedelta(tolerance)}) but too small to confidently treat as an"
        + f" unrelated event (raise threshold {fmt_timedelta(raise_tolerance)})."
        + " This usually indicates a timing problem in the source data; check "
        + "it before importing. If these are known to be genuinely distinct "
        + "events, set 'event_duplicate_strict' to skip this check."
    )


def _find_event(
    session: Session,
    time: Timestamp,
    *,
    label: str,
    known_event_ids: Collection[UUID] | None = None,
) -> tuple[AimbatEvent | None, str | None]:
    """Look up the event at `time`, returning it with any near-duplicate message.

    An exact time match is returned as it is. Otherwise, unless
    `settings.event_duplicate_strict` is set, the nearest event within
    `settings.event_duplicate_raise_tolerance` is considered: within
    `settings.event_duplicate_tolerance` it is returned with a warning.

    Args:
        session: Database session.
        time: Origin time to look up.
        label: Names the source of `time` in messages.
        known_event_ids: Events eligible for a near-duplicate match. All
            events if `None`.

    Returns:
        The event, or `None`, and the near-duplicate message if one was
        reused.

    Raises:
        ValueError: If the nearest event lies between the two tolerances.
    """
    exact = session.exec(
        select(AimbatEvent).where(col(AimbatEvent.time) == time)
    ).one_or_none()
    if exact is not None or settings.event_duplicate_strict:
        return exact, None

    tolerance = settings.event_duplicate_tolerance
    raise_tolerance = settings.event_duplicate_raise_tolerance
    near = [
        e
        for e in session.exec(
            select(AimbatEvent).where(
                col(AimbatEvent.time).between(
                    time - raise_tolerance, time + raise_tolerance
                )
            )
        ).all()
        if known_event_ids is None or e.id in known_event_ids
    ]
    if not near:
        return None, None
    closest = min(near, key=lambda e: abs(e.time - time))
    gap = abs(closest.time - time)
    # Strictly less than raise_tolerance: at or beyond it, the gap is treated
    # as fully independent (see the setting's description in _config.py).
    if gap >= raise_tolerance:
        return None, None
    if gap <= tolerance:
        message = _format_reused_near_duplicate_message(
            label, time, closest, gap, tolerance
        )
        logger.warning(message)
        return closest, message
    raise ValueError(
        _format_ambiguous_gap_message(
            label, time, closest, gap, tolerance, raise_tolerance
        )
    )


def find_event(session: Session, time: Timestamp, *, label: str) -> AimbatEvent | None:
    """Look up the event at `time`. Never creates one.

    Uses the tolerances of `data add`: an exact match, or a near duplicate
    within `settings.event_duplicate_tolerance` (with a warning), unless
    `settings.event_duplicate_strict` is set.

    Args:
        session: Database session.
        time: Origin time to look up.
        label: Names the source of `time` in messages.

    Returns:
        The event, or `None` if there is none at that time.

    Raises:
        ValueError: If the nearest event lies in the ambiguous gap between
            `settings.event_duplicate_tolerance` and
            `settings.event_duplicate_raise_tolerance`.
    """
    event, _ = _find_event(session, time, label=label)
    return event


# ----------------------------------------------------------------------------
# Matching
# ----------------------------------------------------------------------------


class MatchStatus(StrEnum):
    """Outcome of matching a pick target to a seismogram."""

    MATCHED = auto()
    """Exactly one seismogram matches."""

    UNMATCHED = auto()
    """The event is known, but no seismogram of it matches."""

    AMBIGUOUS = auto()
    """Several seismograms of the event match."""

    UNRESOLVED = auto()
    """The event is not in the project."""


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Outcome of matching one target."""

    status: MatchStatus
    seismogram: AimbatSeismogram | None = None
    event: AimbatEvent | None = None
    candidates: tuple[UUID, ...] = ()


def _check_station_codes(target: StationEventTarget, station: AimbatStation) -> None:
    """Raise if a code given in `target` differs from `station`'s."""
    for given, stored, what in (
        (target.network, station.network, "network"),
        (target.station, station.name, "station"),
        (target.location, station.location, "location"),
        (target.channel, station.channel, "channel"),
    ):
        if given is not None and given != stored:
            raise ValueError(
                f"The pick's {what} code {given!r} differs from {stored!r} of "
                + f"station {station.id}."
            )


def _candidates(
    session: Session,
    target: StationEventTarget,
    event: AimbatEvent,
    station: AimbatStation | None,
) -> list[AimbatSeismogram]:
    """Seismograms of `event` whose station matches the target."""
    statement = (
        select(AimbatSeismogram)
        .join(AimbatStation)
        .where(col(AimbatSeismogram.event_id) == event.id)
    )
    if station is not None:
        _check_station_codes(target, station)
        statement = statement.where(col(AimbatSeismogram.station_id) == station.id)
    else:
        missing = [
            what
            for value, what in (
                (target.network, "network"),
                (target.station, "station"),
                (target.location, "location"),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                f"The pick has no {', '.join(missing)} code. Give the station."
            )
        statement = statement.where(
            col(AimbatStation.network) == target.network,
            col(AimbatStation.name) == target.station,
            col(AimbatStation.location) == target.location,
        )
        if target.channel is not None:
            statement = statement.where(col(AimbatStation.channel) == target.channel)
    return list(session.exec(statement.order_by(col(AimbatSeismogram.id))).all())


def match_target(
    session: Session,
    target: PickTarget | None,
    *,
    source_seismogram: AimbatSeismogram | None = None,
    event: AimbatEvent | None = None,
    station: AimbatStation | None = None,
    label: str,
) -> MatchResult:
    """Resolve a pick target to a seismogram.

    A pick without a target belongs to the seismogram of its own source. A
    seismogram ID names the seismogram directly. A station code with an
    event time is matched to the seismograms of that event recorded at that
    station.

    Args:
        session: Database session.
        target: Target as read, or `None` for the pick's own source.
        source_seismogram: Seismogram of the pick's own source.
        event: Event to use instead of the target's event time.
        station: Station to use instead of the target's station code.
        label: Names the pick's source in messages.

    Returns:
        The match.

    Raises:
        ValueError: For a target that cannot be valid: no seismogram for a
            pick without a target, an unknown seismogram ID, a seismogram
            outside `event` or `station`, codes that contradict `station`,
            an event time that contradicts `event`, an incomplete station
            code, or an event time in the ambiguous gap.
    """
    if target is None:
        if source_seismogram is None:
            raise ValueError(
                f"A pick from {label} names no seismogram, and {label} has none."
            )
        return MatchResult(
            MatchStatus.MATCHED, source_seismogram, source_seismogram.event
        )

    if isinstance(target, SeismogramTarget):
        seismogram = session.get(AimbatSeismogram, target.seismogram_id)
        if seismogram is None:
            raise ValueError(f"No seismogram found with ID {target.seismogram_id}.")
        if event is not None and seismogram.event_id != event.id:
            raise ValueError(
                f"Seismogram {seismogram.id} does not belong to event {event.id}."
            )
        if station is not None and seismogram.station_id != station.id:
            raise ValueError(
                f"Seismogram {seismogram.id} was not recorded at station "
                + f"{station.id}."
            )
        return MatchResult(MatchStatus.MATCHED, seismogram, seismogram.event)

    if event is not None:
        if target.event_time is not None:
            found = find_event(session, target.event_time, label=label)
            if found is None or found.id != event.id:
                raise ValueError(
                    f"The pick's event time {target.event_time} does not belong "
                    + f"to event {event.id}."
                )
        resolved = event
    elif target.event_time is None:
        raise ValueError("The pick has no event time. Give the event.")
    else:
        found = find_event(session, target.event_time, label=label)
        if found is None:
            return MatchResult(MatchStatus.UNRESOLVED)
        resolved = found

    candidates = _candidates(session, target, resolved, station)
    if not candidates:
        return MatchResult(MatchStatus.UNMATCHED, event=resolved)
    if len(candidates) > 1:
        return MatchResult(
            MatchStatus.AMBIGUOUS,
            event=resolved,
            candidates=tuple(s.id for s in candidates),
        )
    return MatchResult(MatchStatus.MATCHED, candidates[0], resolved)


# ----------------------------------------------------------------------------
# Storing
# ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PickChange:
    """A stored pick whose data source now gives another time or label."""

    pick: AimbatPick
    """The stored pick."""

    read: SourcePick
    """The pick as the data source now gives it."""


@dataclass(frozen=True, slots=True)
class StoreReport:
    """What `store_picks` wrote."""

    stored: list[AimbatPick] = field(default_factory=list)
    """Picks written."""

    already_present: int = 0
    """Picks skipped because their source and key are already stored.

    Either unchanged or dismissed.
    """

    skipped_unnamed: int = 0
    """Unnamed picks not stored, as asked."""

    changed: list[PickChange] = field(default_factory=list)
    """Stored picks whose time or label differs from the data source.

    Dismissed picks are not among them. The picks are left as they are.
    """

    @classmethod
    def merge(cls, reports: Iterable["StoreReport"]) -> "StoreReport":
        """Combine the reports of several sources."""
        reports = list(reports)
        return cls(
            [pick for report in reports for pick in report.stored],
            sum(report.already_present for report in reports),
            sum(report.skipped_unnamed for report in reports),
            [change for report in reports for change in report.changed],
        )


def _same_time(a: Timestamp, b: Timestamp) -> bool:
    """Whether two times are equal at the stored precision."""
    return bool(a.round("us") == b.round("us"))


def _describe(pick: SourcePick, source_name: str) -> str:
    return f"pick {pick.key!r} of {source_name}"


def store_picks(
    session: Session,
    picks: Sequence[SourcePick],
    *,
    source_name: str,
    source_type: DataType,
    naming: PickNaming = PickNaming(),
    source_seismogram: AimbatSeismogram | None = None,
    source_end_time: Timestamp | None = None,
    event: AimbatEvent | None = None,
    station: AimbatStation | None = None,
) -> StoreReport:
    """Name, match, check and write the raw picks of one source.

    Picks whose source and key are already stored are skipped. Those that
    are not dismissed and whose time or label differs are reported as
    changed. Matched picks
    must not lie before the begin time of their seismogram, nor after
    `source_end_time` when matched to `source_seismogram`. Nothing is
    promoted.

    Args:
        session: Database session.
        picks: Picks read from the source.
        source_name: Name of the source.
        source_type: Data type of the source.
        naming: How picks are named.
        source_seismogram: Seismogram built from the same source, if any.
        source_end_time: End time of `source_seismogram`, if known.
        event: Event to match natural-key targets in.
        station: Station to match natural-key targets at.

    Returns:
        What was written.

    Raises:
        ValueError: If a key occurs twice, a target is invalid or ambiguous,
            a matched pick lies outside its seismogram, or two picks of the
            source give the same seismogram and phase different times.
    """
    keys = [p.key for p in picks]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise ValueError(
            f"{source_name} has more than one pick with key "
            + f"{', '.join(repr(k) for k in duplicates)}."
        )

    present = {
        stored.source_key: stored
        for stored in session.exec(
            select(AimbatPick).where(col(AimbatPick.source_name) == source_name)
        ).all()
    }

    stored: list[AimbatPick] = []
    changed: list[PickChange] = []
    already_present = skipped_unnamed = 0
    ambiguous: list[str] = []
    slots: dict[tuple[UUID, str], SourcePick] = {}

    for pick in picks:
        if (existing := present.get(pick.key)) is not None:
            if existing.dismissed or (
                _same_time(existing.time, pick.time) and existing.label == pick.label
            ):
                already_present += 1
            else:
                changed.append(PickChange(existing, pick))
            continue
        name = naming.name_for(pick)
        if name is None and naming.skip_unnamed:
            skipped_unnamed += 1
            continue

        match = match_target(
            session,
            pick.target,
            source_seismogram=source_seismogram,
            event=event,
            station=station,
            label=source_name,
        )
        if match.status is MatchStatus.AMBIGUOUS:
            ambiguous.append(
                f"{_describe(pick, source_name)} matches seismograms "
                + ", ".join(str(c) for c in match.candidates)
            )
            continue

        seismogram = match.seismogram
        if seismogram is not None:
            if pick.time < seismogram.begin_time:
                raise ValueError(
                    f"The {_describe(pick, source_name)} at {pick.time} lies "
                    + f"before the begin time of seismogram {seismogram.id}."
                )
            if (
                source_end_time is not None
                and seismogram is source_seismogram
                and pick.time > source_end_time
            ):
                raise ValueError(
                    f"The {_describe(pick, source_name)} at {pick.time} lies "
                    + f"after the end time of seismogram {seismogram.id}."
                )
            if name is not None:
                other = slots.setdefault((seismogram.id, name), pick)
                if other is not pick and not _same_time(other.time, pick.time):
                    raise ValueError(
                        f"{source_name} gives seismogram {seismogram.id} two "
                        + f"different {name} picks ({other.key!r} and "
                        + f"{pick.key!r})."
                    )

        stored.append(
            _raw_pick(
                pick,
                name,
                source_name=source_name,
                source_type=source_type,
                seismogram=seismogram,
                event=match.event if seismogram is None else None,
            )
        )

    if ambiguous:
        raise ValueError(
            "Picks match more than one seismogram: " + "; ".join(ambiguous) + "."
        )

    session.add_all(stored)
    session.flush()
    return StoreReport(stored, already_present, skipped_unnamed, changed)


def _raw_pick(
    pick: SourcePick,
    name: str | None,
    *,
    source_name: str,
    source_type: DataType,
    seismogram: AimbatSeismogram | None,
    event: AimbatEvent | None,
) -> AimbatPick:
    """Build the raw record of a source pick."""
    target = pick.target
    by_codes = target if isinstance(target, StationEventTarget) else None
    return AimbatPick(
        time=pick.time,
        label=pick.label,
        phase_name=name,
        origin=PickOrigin.SOURCE,
        source_name=source_name,
        source_type=source_type,
        source_key=pick.key,
        target_network=by_codes.network if by_codes else None,
        target_station=by_codes.station if by_codes else None,
        target_location=by_codes.location if by_codes else None,
        target_channel=by_codes.channel if by_codes else None,
        target_event_time=by_codes.event_time if by_codes else None,
        target_seismogram_id=(
            target.seismogram_id if isinstance(target, SeismogramTarget) else None
        ),
        seismogram_id=seismogram.id if seismogram else None,
        event_id=event.id if event else None,
    )


def _stored_target(pick: AimbatPick) -> StationEventTarget:
    """The natural-key target a raw pick was read with."""
    return StationEventTarget(
        network=pick.target_network,
        station=pick.target_station,
        location=pick.target_location,
        channel=pick.target_channel,
        event_time=pick.target_event_time,
    )


def _has_natural_key(pick: AimbatPick) -> bool:
    """Whether the pick was read with a station code target."""
    return pick.target_seismogram_id is None and any(
        value is not None
        for value in (
            pick.target_network,
            pick.target_station,
            pick.target_location,
            pick.target_channel,
            pick.target_event_time,
        )
    )


def rematch_picks(
    session: Session, *, event_ids: Collection[UUID] | None = None
) -> list[AimbatPick]:
    """Retry matching unmatched picks read with a station code.

    Covers the unmatched picks of `event_ids` (all events if `None`) and
    every pick whose event is not known. A pick that now matches a
    seismogram it lies before is left unmatched and logged. Never raises.

    Args:
        session: Database session.
        event_ids: Events whose unmatched picks are retried.

    Returns:
        The picks matched by this call.
    """
    statement = select(AimbatPick).where(
        col(AimbatPick.seismogram_id).is_(None),
        col(AimbatPick.dismissed).is_(False),
        col(AimbatPick.target_seismogram_id).is_(None),
    )
    if event_ids is not None:
        statement = statement.where(
            or_(
                col(AimbatPick.event_id).is_(None),
                col(AimbatPick.event_id).in_(list(event_ids)),
            )
        )

    matched: list[AimbatPick] = []
    for pick in session.exec(statement.order_by(col(AimbatPick.id))).all():
        if not _has_natural_key(pick):
            continue
        label = pick.source_name or f"pick {pick.id}"
        known = session.get(AimbatEvent, pick.event_id) if pick.event_id else None
        try:
            match = match_target(
                session, _stored_target(pick), event=known, label=label
            )
        except ValueError as exc:
            logger.info(f"Pick {pick.id} stays unmatched: {exc}")
            continue
        if match.status is MatchStatus.MATCHED and match.seismogram is not None:
            if pick.time < match.seismogram.begin_time:
                logger.info(
                    f"Pick {pick.id} stays unmatched: it lies before the begin "
                    + f"time of seismogram {match.seismogram.id}."
                )
                continue
            pick.seismogram_id = match.seismogram.id
            pick.event_id = None
            matched.append(pick)
        elif match.event is not None and pick.event_id != match.event.id:
            pick.event_id = match.event.id
        session.add(pick)

    session.flush()
    return matched


# ----------------------------------------------------------------------------
# Promotion
# ----------------------------------------------------------------------------


def _phase_for(
    session: Session, seismogram: AimbatSeismogram, name: str
) -> AimbatPhase | None:
    """Return the phase a seismogram's pick named `name` belongs to, if it exists."""
    return session.exec(
        select(AimbatPhase).where(
            col(AimbatPhase.event_id) == seismogram.event_id,
            col(AimbatPhase.name) == name,
            col(AimbatPhase.component) == phase_component(seismogram.station),
        )
    ).one_or_none()


def _row_of(
    session: Session, seismogram_id: UUID, phase_id: UUID
) -> AimbatSeismogramParameters | None:
    return session.exec(
        select(AimbatSeismogramParameters).where(
            col(AimbatSeismogramParameters.seismogram_id) == seismogram_id,
            col(AimbatSeismogramParameters.phase_id) == phase_id,
        )
    ).one_or_none()


def _is_promoted(session: Session, pick: AimbatPick) -> bool:
    return (
        session.exec(
            select(AimbatSeismogramParameters.id).where(
                col(AimbatSeismogramParameters.pick_id) == pick.id
            )
        ).first()
        is not None
    )


@dataclass(frozen=True, slots=True)
class PickCheck:
    """Result of `validate_pick`."""

    errors: tuple[str, ...] = ()
    """Why the pick cannot be the initial pick of the seismogram."""

    conflict: AimbatSeismogramParameters | None = None
    """Row of the slot holding a pick with a different time, if any."""

    redundant: bool = False
    """Whether the slot already holds a pick with the same time."""


def validate_pick(
    session: Session,
    pick: AimbatPick,
    seismogram: AimbatSeismogram,
    *,
    end_time: Timestamp | None = None,
) -> PickCheck:
    """Check whether a pick can be the initial pick of a seismogram.

    Args:
        session: Database session.
        pick: The pick.
        seismogram: The seismogram.
        end_time: End time of the seismogram, if known.

    Returns:
        The errors found, and how the pick relates to the row the seismogram
        has for the pick's phase, if any.
    """
    errors: list[str] = []
    if pick.event_id is not None and pick.event_id != seismogram.event_id:
        errors.append(
            f"Seismogram {seismogram.id} belongs to event {seismogram.event_id}, "
            + f"the pick to event {pick.event_id}."
        )
    if pick.time < seismogram.begin_time:
        errors.append(
            f"The pick at {pick.time} lies before the begin time of seismogram "
            + f"{seismogram.id}."
        )
    if end_time is not None and pick.time > end_time:
        errors.append(
            f"The pick at {pick.time} lies after the end time of seismogram "
            + f"{seismogram.id}."
        )
    if pick.phase_name is not None:
        try:
            validate_phase_name(pick.phase_name)
        except ValueError as exc:
            errors.append(str(exc))

    conflict: AimbatSeismogramParameters | None = None
    redundant = False
    if pick.phase_name is not None:
        phase = _phase_for(session, seismogram, pick.phase_name)
        row = _row_of(session, seismogram.id, phase.id) if phase else None
        if row is not None and row.pick_id != pick.id:
            if _same_time(row.pick.time, pick.time):
                redundant = True
            else:
                conflict = row
    return PickCheck(tuple(errors), conflict, redundant)


@dataclass(frozen=True, slots=True)
class PromotionReport:
    """What `promote_picks` did."""

    rows: list[AimbatSeismogramParameters] = field(default_factory=list)
    """Rows created."""

    phases_created: list[AimbatPhase] = field(default_factory=list)
    """Phases created."""

    conflicts: list[AimbatPick] = field(default_factory=list)
    """Picks not promoted because the row holds a pick with another time."""

    unpromoted: list[AimbatPick] = field(default_factory=list)
    """Picks not promoted because their phase is not among those allowed."""

    invalid: list[AimbatPick] = field(default_factory=list)
    """Picks not promoted because `validate_pick` found errors."""

    replaced: list[AimbatPick] = field(default_factory=list)
    """Picks dismissed because another pick took over their row."""

    warnings: list[str] = field(default_factory=list)
    """Things the caller should know about, which did not stop the change."""


def promote_picks(
    session: Session,
    picks: Iterable[AimbatPick],
    *,
    phases: bool | Collection[str] = True,
) -> PromotionReport:
    """Create rows for the picks that are matched, named, not dismissed and not promoted.

    Picks are taken in order of source, then key. `phases` sets the phases
    that may gain rows: every phase if `True`, only existing phases if
    `False`, or only the phases named. A missing phase that is allowed is
    created, with a warning if its name is not a standard phase name
    ([`is_standard_phase`][pysmo.tools.traveltime.is_standard_phase]).
    Phases are per event, name and component: a pick belongs to the phase of
    its name on its seismogram's component (`phase_component`). A pick that
    fails `validate_pick` is not promoted. A pick whose seismogram
    already has a row for the phase is redundant if that row's pick has the
    same time, and a conflict otherwise.

    Args:
        session: Database session.
        picks: Picks to promote. Others among them are ignored.
        phases: Which phases may gain rows, or be created.

    Returns:
        What was created, and the picks left out.
    """
    report = PromotionReport()
    allowed = None if isinstance(phases, bool) else set(phases)
    phases_seen: dict[tuple[UUID, str, str], AimbatPhase] = {}
    rows: dict[tuple[UUID, UUID], AimbatSeismogramParameters] = {}

    ordered = sorted(picks, key=lambda p: (p.source_name or "", p.source_key or ""))
    for pick in ordered:
        if (
            pick.dismissed
            or pick.seismogram_id is None
            or pick.phase_name is None
            or _is_promoted(session, pick)
        ):
            continue
        seismogram = session.get(AimbatSeismogram, pick.seismogram_id)
        if seismogram is None:
            continue
        if validate_pick(session, pick, seismogram).errors:
            report.invalid.append(pick)
            continue

        if allowed is not None and pick.phase_name not in allowed:
            report.unpromoted.append(pick)
            continue
        component = phase_component(seismogram.station)
        phase_key = (seismogram.event_id, pick.phase_name, component)
        phase = phases_seen.get(phase_key) or _phase_for(
            session, seismogram, pick.phase_name
        )

        if phase is None:
            if phases is False:
                report.unpromoted.append(pick)
                continue
            # The relationship, not just the ID, so the event stays readable
            # after a dry run rolls the phase back.
            phase = AimbatPhase(
                event_id=seismogram.event_id,
                event=seismogram.event,
                name=pick.phase_name,
                component=component,
                parameters=default_phase_parameters(pick.phase_name, component),
            )
            session.add(phase)
            report.phases_created.append(phase)
            _warn_nonstandard_phase(report, pick.phase_name)
        phases_seen[phase_key] = phase

        row_key = (seismogram.id, phase.id)
        row = rows.get(row_key) or _row_of(session, *row_key)
        if row is not None:
            if not _same_time(row.pick.time, pick.time):
                report.conflicts.append(pick)
            continue
        row = AimbatSeismogramParameters(
            seismogram_id=seismogram.id, phase=phase, pick=pick
        )
        session.add(row)
        rows[row_key] = row
        report.rows.append(row)

    session.flush()
    return report


def _warn_nonstandard_phase(report: PromotionReport, phase_name: str) -> None:
    """Warn in the report and the log, once, if pysmo does not list the phase name."""
    if is_standard_phase(phase_name):
        return
    message = f"Phase name {phase_name!r} is not in the IASPEI standard phase list."
    if message not in report.warnings:
        logger.warning(message)
        report.warnings.append(message)


# ----------------------------------------------------------------------------
# States
# ----------------------------------------------------------------------------


class PickState(StrEnum):
    """State of a raw pick, derived from the stored data."""

    PROMOTED = auto()
    """The initial pick of a row."""

    UNPROMOTED = auto()
    """Named and matched, without a row: its phase does not exist."""

    UNNAMED = auto()
    """Matched, but no phase name assigned."""

    UNMATCHED = auto()
    """Its event is known, but no seismogram of it matches."""

    AMBIGUOUS = auto()
    """Several seismograms of its event match."""

    UNRESOLVED = auto()
    """Its event is not in the project."""

    CONFLICT = auto()
    """The row for its seismogram and phase holds a pick with another time."""

    REDUNDANT = auto()
    """The row for its seismogram and phase holds a pick with the same time."""

    DISMISSED = auto()
    """Excluded from promotion and checks."""


def _unmatched_state(session: Session, pick: AimbatPick) -> PickState:
    """State of a pick with no seismogram."""
    if pick.event_id is None:
        return PickState.UNRESOLVED
    event = session.get(AimbatEvent, pick.event_id)
    if event is None or not _has_natural_key(pick):
        return PickState.UNMATCHED
    try:
        candidates = _candidates(session, _stored_target(pick), event, None)
    except ValueError:
        return PickState.UNMATCHED
    return PickState.AMBIGUOUS if len(candidates) > 1 else PickState.UNMATCHED


def pick_states(
    session: Session,
    *,
    event_id: UUID | None = None,
    pick_ids: Collection[UUID] | None = None,
) -> dict[UUID, PickState]:
    """Derive the state of each pick.

    Args:
        session: Database session.
        event_id: Only the picks of this event: those matched to its
            seismograms and the unmatched ones assigned to it.
        pick_ids: Only these picks.

    Returns:
        The state of each selected pick, by pick ID.
    """
    statement = select(AimbatPick).outerjoin(
        AimbatSeismogram, col(AimbatSeismogram.id) == col(AimbatPick.seismogram_id)
    )
    if event_id is not None:
        statement = statement.where(
            or_(
                col(AimbatSeismogram.event_id) == event_id,
                col(AimbatPick.event_id) == event_id,
            )
        )
    if pick_ids is not None:
        statement = statement.where(col(AimbatPick.id).in_(list(pick_ids)))

    states: dict[UUID, PickState] = {}
    for pick in session.exec(statement).all():
        if pick.dismissed:
            states[pick.id] = PickState.DISMISSED
        elif _is_promoted(session, pick):
            states[pick.id] = PickState.PROMOTED
        elif pick.seismogram_id is None:
            states[pick.id] = _unmatched_state(session, pick)
        elif pick.phase_name is None:
            states[pick.id] = PickState.UNNAMED
        else:
            own = session.get(AimbatSeismogram, pick.seismogram_id)
            if own is None:
                states[pick.id] = PickState.UNPROMOTED
                continue
            check = validate_pick(session, pick, own)
            if check.redundant:
                states[pick.id] = PickState.REDUNDANT
            elif check.conflict is not None:
                states[pick.id] = PickState.CONFLICT
            else:
                states[pick.id] = PickState.UNPROMOTED
    return states
