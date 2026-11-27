"""Select and fix stored picks.

These functions complete the picks of a project after ingestion: they name
unnamed picks, match unmatched ones, promote named, matched picks that have
no row yet, set manual picks, and dismiss, delete or restore picks.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from pandas import Timedelta, Timestamp
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col, or_, select

from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatPick,
    AimbatPickRead,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    PickOrigin,
)
from aimbat.utils import check_field_name_flags, dump_models

from ._picks import (
    PromotionReport,
    _is_promoted,
    _phase_for,
    _row_of,
    _warn_nonstandard_phase,
    find_event,
    pick_states,
    promote_picks,
    rematch_picks,
    validate_phase_name,
    validate_pick,
)
from ._session import flush_deletes

__all__ = [
    "PickSelection",
    "RemovalReport",
    "dump_pick_table",
    "match_pick",
    "name_picks",
    "promote_existing_picks",
    "promote_phase_picks",
    "remove_picks",
    "restore_picks",
    "retry_pick_matching",
    "select_picks",
    "set_initial_pick",
]


def _utc(bound: Timestamp | Timedelta | None) -> Timestamp | Timedelta | None:
    if isinstance(bound, Timestamp):
        if bound.tzinfo is None:
            raise ValueError(f"Time {bound} has no time zone.")
        return bound.tz_convert("UTC")
    return bound


@dataclass(frozen=True, slots=True)
class PickSelection:
    """Which stored picks a command acts on.

    A pick is selected if it meets every criterion given. Picks are never
    selected by their source key. A time bound given as a `Timedelta` counts
    from the origin time of the pick's event, and leaves out picks whose
    event is not known.
    """

    pick_ids: tuple[UUID, ...] = ()
    """Only these picks."""

    event_id: UUID | None = None
    """Only the picks of this event."""

    seismogram_ids: tuple[UUID, ...] = ()
    """Only picks matched to these seismograms."""

    station_ids: tuple[UUID, ...] = ()
    """Only picks matched to seismograms of these stations."""

    label: str | None = None
    """Only picks read with this label."""

    phase_name: str | None = None
    """Only picks with this phase name."""

    unnamed: bool = False
    """Only picks without a phase name."""

    unmatched: bool = False
    """Only picks not matched to a seismogram."""

    dismissed: bool | None = False
    """Only dismissed picks if `True`, only other picks if `False`, both if `None`."""

    time_from: Timestamp | Timedelta | None = None
    """Only picks at or after this time."""

    time_to: Timestamp | Timedelta | None = None
    """Only picks at or before this time."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "time_from", _utc(self.time_from))
        object.__setattr__(self, "time_to", _utc(self.time_to))

    @property
    def has_criteria(self) -> bool:
        """Whether any criterion other than `dismissed` is given."""
        return bool(
            self.pick_ids
            or self.event_id is not None
            or self.seismogram_ids
            or self.station_ids
            or self.label is not None
            or self.phase_name is not None
            or self.unnamed
            or self.unmatched
            or self.time_from is not None
            or self.time_to is not None
        )


def _event_time(session: Session, pick: AimbatPick) -> Timestamp | None:
    """Origin time of the pick's event, or `None` if it is not known."""
    if pick.seismogram_id is not None:
        seismogram = session.get(AimbatSeismogram, pick.seismogram_id)
        return seismogram.event.time if seismogram is not None else None
    if pick.event_id is not None:
        event = session.get(AimbatEvent, pick.event_id)
        return event.time if event is not None else None
    return None


def _within(session: Session, pick: AimbatPick, selection: PickSelection) -> bool:
    """Whether the pick lies within the relative time bounds of the selection."""
    origin = _event_time(session, pick)
    if origin is None:
        return False
    if isinstance(selection.time_from, Timedelta):
        if pick.time < origin + selection.time_from:
            return False
    if isinstance(selection.time_to, Timedelta):
        if pick.time > origin + selection.time_to:
            return False
    return True


def _query(session: Session, selection: PickSelection) -> list[AimbatPick]:
    """The picks the selection describes, by time."""
    statement = select(AimbatPick).outerjoin(
        AimbatSeismogram, col(AimbatSeismogram.id) == col(AimbatPick.seismogram_id)
    )
    if selection.dismissed is not None:
        statement = statement.where(col(AimbatPick.dismissed).is_(selection.dismissed))
    if selection.pick_ids:
        statement = statement.where(col(AimbatPick.id).in_(selection.pick_ids))
    if selection.event_id is not None:
        statement = statement.where(
            or_(
                col(AimbatSeismogram.event_id) == selection.event_id,
                col(AimbatPick.event_id) == selection.event_id,
            )
        )
    if selection.seismogram_ids:
        statement = statement.where(
            col(AimbatPick.seismogram_id).in_(selection.seismogram_ids)
        )
    if selection.station_ids:
        statement = statement.where(
            col(AimbatSeismogram.station_id).in_(selection.station_ids)
        )
    if selection.label is not None:
        statement = statement.where(col(AimbatPick.label) == selection.label)
    if selection.phase_name is not None:
        statement = statement.where(col(AimbatPick.phase_name) == selection.phase_name)
    if selection.unnamed:
        statement = statement.where(col(AimbatPick.phase_name).is_(None))
    if selection.unmatched:
        statement = statement.where(col(AimbatPick.seismogram_id).is_(None))
    if isinstance(selection.time_from, Timestamp):
        statement = statement.where(col(AimbatPick.time) >= selection.time_from)
    if isinstance(selection.time_to, Timestamp):
        statement = statement.where(col(AimbatPick.time) <= selection.time_to)

    picks = list(
        session.exec(statement.order_by(col(AimbatPick.time), col(AimbatPick.id))).all()
    )
    if isinstance(selection.time_from, Timedelta) or isinstance(
        selection.time_to, Timedelta
    ):
        picks = [pick for pick in picks if _within(session, pick, selection)]
    return picks


def _ids(ids: Sequence[UUID]) -> str:
    return ", ".join(map(str, ids))


def select_picks(session: Session, selection: PickSelection) -> list[AimbatPick]:
    """Return the picks a selection describes, by time.

    Args:
        session: Database session.
        selection: The selection.

    Raises:
        ValueError: If the selection has no criteria, or a pick it names is
            dismissed while `selection.dismissed` is `False` (or the other
            way round).
        NoResultFound: If a pick it names does not exist.
    """
    if not selection.has_criteria:
        raise ValueError("A pick selection needs at least one criterion.")
    if selection.pick_ids:
        flags = dict(
            session.exec(
                select(AimbatPick.id, AimbatPick.dismissed).where(
                    col(AimbatPick.id).in_(selection.pick_ids)
                )
            ).all()
        )
        missing = [i for i in selection.pick_ids if i not in flags]
        if missing:
            raise NoResultFound(f"No pick found with ID {_ids(missing)}.")
        if selection.dismissed is not None:
            other = [i for i, flag in flags.items() if flag != selection.dismissed]
            if other:
                state = "not dismissed" if selection.dismissed else "dismissed"
                raise ValueError(f"These picks are {state}: {_ids(other)}.")
    return _query(session, selection)


def dump_pick_table(
    session: Session,
    from_read_model: bool = False,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    selection: PickSelection | None = None,
) -> list[dict[str, Any]]:
    """Dump the stored picks, with their state, to a JSON-serialisable list of dicts.

    Each record carries the derived state of its pick (`PickState`) as
    `state`.

    Args:
        session: Database session.
        from_read_model: Whether to dump from the read model (True) or the ORM model.
        by_alias: Whether to use serialisation aliases for the field names.
        by_title: Whether to use the field title metadata for the field names
            (only applicable when from_read_model is True). Mutually exclusive
            with by_alias.
        exclude: Set of field names to exclude from the output.
        selection: Picks to dump, of which no criterion is required. Every
            pick, dismissed or not, if `None`.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
        ValueError: If `by_title` is True but `from_read_model` is False.
    """
    logger.debug("Dumping AIMBAT pick table to json.")

    check_field_name_flags(by_alias, by_title, from_read_model)

    picks = _query(session, selection or PickSelection(dismissed=None))
    states = pick_states(session, pick_ids=[pick.id for pick in picks])
    if from_read_model:
        reads = [
            AimbatPickRead.from_pick(
                pick, str(states[pick.id]), _event_time(session, pick), session
            )
            for pick in picks
        ]
        return dump_models(
            reads, AimbatPickRead, by_alias=by_alias, by_title=by_title, exclude=exclude
        )
    records = dump_models(picks, AimbatPick, by_alias=by_alias, exclude=exclude)
    for pick, record in zip(picks, records, strict=True):
        record["state"] = str(states[pick.id])
    return records


def name_picks(
    session: Session, picks: Sequence[AimbatPick], phase_name: str
) -> PromotionReport:
    """Give picks a phase name, and promote those that are matched.

    Phases missing for the picks are created. The labels the picks were read
    with are kept. A name that is not a standard phase name is accepted with
    a warning.

    Args:
        session: Database session.
        picks: Picks to name. None of them may be promoted or dismissed.
        phase_name: The phase name.

    Returns:
        What promoting the named picks did.

    Raises:
        ValueError: If the name is not a valid phase name, or a pick is
            promoted or dismissed. Nothing is changed.
    """
    name = validate_phase_name(phase_name)
    dismissed = [pick.id for pick in picks if pick.dismissed]
    if dismissed:
        raise ValueError(f"Dismissed picks cannot be named: {_ids(dismissed)}.")
    promoted = [pick.id for pick in picks if _is_promoted(session, pick)]
    if promoted:
        raise ValueError(
            f"Promoted picks keep the name of their phase: {_ids(promoted)}. "
            + "`aimbat phase rename` renames a phase together with its picks."
        )
    for pick in picks:
        pick.phase_name = name
        session.add(pick)
    session.flush()
    report = promote_picks(session, picks)
    _warn_nonstandard_phase(report, name)
    return report


def promote_phase_picks(
    session: Session, phase_name: str, *, event_id: UUID | None = None
) -> PromotionReport:
    """Promote the matched picks named for a phase, creating the phase where missing.

    Args:
        session: Database session.
        phase_name: The phase name.
        event_id: Only the picks of this event. Every event's if `None`.

    Returns:
        What promotion did.

    Raises:
        ValueError: If the name is not a valid phase name.
    """
    name = validate_phase_name(phase_name)
    picks = _query(session, PickSelection(event_id=event_id, phase_name=name))
    return promote_picks(session, picks, phases={name})


def promote_existing_picks(
    session: Session, pick_ids: Sequence[UUID], *, replace_rows: bool = False
) -> PromotionReport:
    """Promote the given picks, creating their phases where missing.

    A pick whose seismogram already has a row for its phase, holding a pick
    with another time, is a conflict. With `replace_rows`, it takes over that
    row instead, and the pick it replaces is dismissed. The row keeps its
    other values. Picks already promoted are left as they are.

    Args:
        session: Database session.
        pick_ids: IDs of the picks.
        replace_rows: Whether conflicting picks take over the rows.

    Returns:
        What promotion did, with the picks replaced.

    Raises:
        NoResultFound: If a pick does not exist.
        ValueError: If a pick is dismissed, unnamed or unmatched, or, with
            `replace_rows`, two picks are for the same seismogram and phase.
            Nothing is changed.
    """
    picks = select_picks(session, PickSelection(pick_ids=tuple(pick_ids)))
    unmatched = [pick.id for pick in picks if pick.seismogram_id is None]
    if unmatched:
        raise ValueError(
            f"These picks are not matched to a seismogram: {_ids(unmatched)}."
        )
    unnamed = [pick.id for pick in picks if pick.phase_name is None]
    if unnamed:
        raise ValueError(f"These picks have no phase name: {_ids(unnamed)}.")

    replaced: list[AimbatPick] = []
    if replace_rows:
        pending = [pick for pick in picks if not _is_promoted(session, pick)]
        slots: dict[tuple[UUID | None, str | None], UUID] = {}
        for pick in pending:
            slot = (pick.seismogram_id, pick.phase_name)
            if slot in slots:
                raise ValueError(
                    f"Picks {slots[slot]} and {pick.id} are for the same "
                    + "seismogram and phase."
                )
            slots[slot] = pick.id
        for pick in pending:
            seismogram = session.get_one(AimbatSeismogram, pick.seismogram_id)
            check = validate_pick(session, pick, seismogram)
            if check.errors or check.conflict is None:
                continue
            row = check.conflict
            old = row.pick
            old.dismissed = True
            row.pick = pick
            session.add_all([old, row])
            replaced.append(old)
        session.flush()

    report = promote_picks(session, picks)
    return replace(report, replaced=replaced)


def _event_of_unmatched(session: Session, pick: AimbatPick) -> AimbatEvent | None:
    """The event of an unmatched pick, or `None` if it is not in the project."""
    if pick.event_id is not None:
        return session.get(AimbatEvent, pick.event_id)
    if pick.target_event_time is None:
        return None
    label = pick.source_name or f"pick {pick.id}"
    return find_event(session, pick.target_event_time, label=label)


def _code_warnings(pick: AimbatPick, seismogram: AimbatSeismogram) -> list[str]:
    """Differences between the station code a pick was read with and the seismogram's."""
    station = seismogram.station
    warnings = []
    for given, stored, what in (
        (pick.target_network, station.network, "network"),
        (pick.target_station, station.name, "station"),
        (pick.target_location, station.location, "location"),
        (pick.target_channel, station.channel, "channel"),
    ):
        if given is not None and given != stored:
            warnings.append(
                f"Pick {pick.id} was read with {what} code {given!r}, seismogram "
                + f"{seismogram.id} has {stored!r}."
            )
    return warnings


def match_pick(session: Session, pick_id: UUID, seismogram_id: UUID) -> PromotionReport:
    """Match an unmatched pick to a seismogram of its event, and promote it if named.

    A station code the pick was read with that differs from the
    seismogram's is reported as a warning.

    Args:
        session: Database session.
        pick_id: ID of the pick.
        seismogram_id: ID of the seismogram.

    Returns:
        What promoting the pick did, with the warnings.

    Raises:
        NoResultFound: If the pick or the seismogram does not exist.
        ValueError: If the pick is dismissed or already matched, its event is
            not the seismogram's, or it fails the pick checks for the
            seismogram. Nothing is changed.
    """
    (pick,) = select_picks(session, PickSelection(pick_ids=(pick_id,)))
    seismogram = session.get(AimbatSeismogram, seismogram_id)
    if seismogram is None:
        raise NoResultFound(f"No seismogram found with ID {seismogram_id}.")
    if pick.seismogram_id is not None:
        raise ValueError(
            f"Pick {pick.id} is already matched to seismogram {pick.seismogram_id}."
        )
    event = _event_of_unmatched(session, pick)
    if event is None:
        raise ValueError(
            f"The event of pick {pick.id} is not in the project. "
            + "`aimbat pick match --retry` matches it once the event is added."
        )
    if event.id != seismogram.event_id:
        raise ValueError(
            f"Pick {pick.id} belongs to event {event.id}, seismogram "
            + f"{seismogram.id} to event {seismogram.event_id}."
        )
    old_event_id = pick.event_id
    with session.no_autoflush:
        pick.event_id = None
        pick.seismogram_id = seismogram.id
        check = validate_pick(session, pick, seismogram)
        if check.errors:
            pick.event_id, pick.seismogram_id = old_event_id, None
            raise ValueError(" ".join(check.errors))
    session.add(pick)
    session.flush()
    report = promote_picks(session, [pick])
    report.warnings.extend(_code_warnings(pick, seismogram))
    return report


def retry_pick_matching(
    session: Session, *, event_id: UUID | None = None
) -> tuple[list[AimbatPick], PromotionReport]:
    """Retry matching the unmatched picks read with a station code, and promote those matched.

    Covers the unmatched picks of the event (every event if `None`) and
    every pick whose event is not known. Phases missing for the picks are
    created.

    Args:
        session: Database session.
        event_id: Only the unmatched picks of this event, and those whose
            event is not known.

    Returns:
        The picks matched, and what promoting them did.
    """
    matched = rematch_picks(session, event_ids=None if event_id is None else [event_id])
    return matched, promote_picks(session, matched)


def set_initial_pick(
    session: Session,
    seismogram_id: UUID,
    phase_name: str,
    time: Timestamp,
    *,
    replace_row: bool = False,
) -> tuple[AimbatPick, PromotionReport]:
    """Store a manual pick and make it the initial pick of a seismogram for a phase.

    The phase is created if it is missing. With `replace_row`, the manual
    pick takes over an existing row, which keeps its other values, and the
    pick it replaces is dismissed.

    Args:
        session: Database session.
        seismogram_id: ID of the seismogram.
        phase_name: The phase name.
        time: Time of the pick, with a time zone.
        replace_row: Whether to replace the pick of an existing row.

    Returns:
        The manual pick, and what promoting it did, with the pick replaced.

    Raises:
        NoResultFound: If the seismogram does not exist.
        ValueError: If the name is not a valid phase name, the time has no
            time zone or lies before the begin time of the seismogram, or the
            seismogram already has a row for the phase and `replace_row` is
            False. Nothing is changed.
    """
    name = validate_phase_name(phase_name)
    if time.tzinfo is None:
        raise ValueError(f"Time {time} has no time zone.")
    seismogram = session.get(AimbatSeismogram, seismogram_id)
    if seismogram is None:
        raise NoResultFound(f"No seismogram found with ID {seismogram_id}.")

    pick = AimbatPick(
        time=time.tz_convert("UTC"),
        phase_name=name,
        origin=PickOrigin.MANUAL,
        seismogram_id=seismogram.id,
    )
    check = validate_pick(session, pick, seismogram)
    if check.errors:
        raise ValueError(" ".join(check.errors))
    phase = _phase_for(session, seismogram, name)
    row = _row_of(session, seismogram.id, phase.id) if phase else None
    if row is not None and not replace_row:
        raise ValueError(
            f"Seismogram {seismogram.id} already has a {name} pick at "
            + f"{row.pick.time}. `--replace` replaces it."
        )

    session.add(pick)
    if row is None:
        session.flush()
        return pick, promote_picks(session, [pick])
    old = row.pick
    old.dismissed = True
    row.pick = pick
    session.add_all([old, row])
    session.flush()
    return pick, PromotionReport(replaced=[old])


@dataclass(frozen=True, slots=True)
class RemovalReport:
    """What `remove_picks` changed."""

    dismissed: list[UUID] = field(default_factory=list)
    """Picks dismissed."""

    purged: list[UUID] = field(default_factory=list)
    """Picks deleted."""

    rows_deleted: int = 0
    """Rows deleted with their picks."""


def remove_picks(
    session: Session, picks: Sequence[AimbatPick], *, purge: bool = False
) -> RemovalReport:
    """Dismiss or delete picks, and delete their rows.

    A dismissed pick is kept, but left out of promotion and of the readiness
    checks. A deleted pick of a data source is stored again when the source
    is read again.

    Args:
        session: Database session.
        picks: Picks to remove. With `purge`, dismissed picks may be among
            them.
        purge: Whether to delete the picks instead of dismissing them.

    Returns:
        The picks dismissed or deleted, and the number of rows deleted.
    """
    ids = [pick.id for pick in picks]
    rows = session.exec(
        select(AimbatSeismogramParameters).where(
            col(AimbatSeismogramParameters.pick_id).in_(ids)
        )
    ).all()
    for row in rows:
        session.delete(row)
    if purge:
        for pick in picks:
            session.delete(pick)
    else:
        for pick in picks:
            pick.dismissed = True
            session.add(pick)
    flush_deletes(session)
    return RemovalReport(
        dismissed=[] if purge else ids,
        purged=ids if purge else [],
        rows_deleted=len(rows),
    )


def restore_picks(session: Session, picks: Sequence[AimbatPick]) -> PromotionReport:
    """Undo the dismissal of picks, and promote those that are named and matched.

    Phases missing for the picks are created.

    Args:
        session: Database session.
        picks: Dismissed picks.

    Returns:
        What promoting the picks did.

    Raises:
        ValueError: If a pick is not dismissed. Nothing is changed.
    """
    kept = [pick.id for pick in picks if not pick.dismissed]
    if kept:
        raise ValueError(f"These picks are not dismissed: {_ids(kept)}.")
    for pick in picks:
        pick.dismissed = False
        session.add(pick)
    session.flush()
    return promote_picks(session, picks)
