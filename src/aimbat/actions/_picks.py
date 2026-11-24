"""Actions that add and edit stored picks, and the results of pick ingestion."""

import os
from collections import Counter
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from dataclasses import replace as replace_fields
from typing import Literal
from uuid import UUID

from pandas import Timestamp
from sqlalchemy import Engine
from sqlmodel import Session

from aimbat import core
from aimbat.core import (
    PickNaming,
    PickSelection,
    PromotionReport,
    StoreReport,
    UpdateReport,
)
from aimbat.io import DataType
from aimbat.models import AimbatPick, AimbatSeismogram

from ._session import open_session

__all__ = [
    "AddPicksResult",
    "CreatedPhase",
    "PickChangeResult",
    "PickSummary",
    "add_picks",
    "match_pick",
    "name_picks",
    "promote_phase_picks",
    "promote_picks",
    "remove_picks",
    "restore_picks",
    "retry_pick_matching",
    "set_initial_pick",
]


@dataclass(frozen=True)
class CreatedPhase:
    """A phase created by promoting picks."""

    event_id: UUID
    event_time: Timestamp
    phase_id: UUID
    name: str


def _created_phases(report: PromotionReport) -> list[CreatedPhase]:
    return [
        CreatedPhase(phase.event_id, phase.event.time, phase.id, phase.name)
        for phase in report.phases_created
    ]


@dataclass(frozen=True)
class PickSummary:
    """What became of the picks of an ingestion call."""

    stored: int = 0
    """Picks written as raw picks."""
    already_present: int = 0
    """Picks skipped because their source and key were already stored."""
    skipped_unnamed: int = 0
    """Unnamed picks not stored, as asked."""
    matched: int = 0
    """Stored picks matched to a seismogram."""
    unmatched: int = 0
    """Stored picks whose event is known but which match no seismogram."""
    unresolved: int = 0
    """Stored picks whose event is not known."""
    named: int = 0
    """Stored picks with a phase name."""
    unnamed: int = 0
    """Stored picks without a phase name."""
    rematched: int = 0
    """Picks stored by earlier calls and matched by this one."""
    changed: int = 0
    """Stored picks whose time or label differs from the data source."""
    updated: int = 0
    """Changed picks given the time and label of the data source."""
    renamed: int = 0
    """Updated picks whose phase name changed with their label."""
    rows_deleted: int = 0
    """Rows deleted because their pick changed its phase name."""
    promoted: dict[str, int] = field(default_factory=dict)
    """Rows created, keyed by phase name."""
    phase_rows: dict[UUID, int] = field(default_factory=dict)
    """Rows created, keyed by phase ID."""
    phases_created: list[CreatedPhase] = field(default_factory=list)
    """Phases created."""
    conflicts: list[UUID] = field(default_factory=list)
    """Picks not promoted because the row holds a pick with another time."""
    unpromoted: list[UUID] = field(default_factory=list)
    """Picks not promoted because their phase is not among those allowed."""
    invalid: list[UUID] = field(default_factory=list)
    """Picks not promoted because they fail the pick checks."""
    warnings: list[str] = field(default_factory=list)
    """Things the caller should know about, which did not stop the change."""

    @property
    def total_promoted(self) -> int:
        """Number of rows created."""
        return sum(self.promoted.values())

    @classmethod
    def from_reports(
        cls,
        stored: StoreReport,
        rematched: list[AimbatPick],
        promotion: PromotionReport,
        updated: UpdateReport | None = None,
    ) -> "PickSummary":
        """Summarise the reports of an ingestion call while its records are loaded."""
        picks = stored.stored
        updated = updated or UpdateReport()
        return cls(
            stored=len(picks),
            already_present=stored.already_present,
            skipped_unnamed=stored.skipped_unnamed,
            matched=sum(p.seismogram_id is not None for p in picks),
            unmatched=sum(
                p.seismogram_id is None and p.event_id is not None for p in picks
            ),
            unresolved=sum(
                p.seismogram_id is None and p.event_id is None for p in picks
            ),
            named=sum(p.phase_name is not None for p in picks),
            unnamed=sum(p.phase_name is None for p in picks),
            rematched=len(rematched),
            changed=len(stored.changed),
            updated=len(updated.updated),
            renamed=len(updated.renamed),
            rows_deleted=updated.rows_deleted,
            promoted=dict(Counter(row.phase.name for row in promotion.rows)),
            phase_rows=dict(Counter(row.phase_id for row in promotion.rows)),
            phases_created=_created_phases(promotion),
            conflicts=[p.id for p in promotion.conflicts],
            unpromoted=[p.id for p in promotion.unpromoted],
            invalid=[p.id for p in promotion.invalid],
            warnings=list(promotion.warnings),
        )


@dataclass(frozen=True)
class AddPicksResult:
    """Outcome of `add_picks`, or of a dry run."""

    sources: list[str]
    """Data sources read."""
    picks: PickSummary
    """What became of the picks read from the data sources."""
    snapshotted_phase_ids: list[UUID]
    """Phases that gained rows and were snapshotted."""
    snapshot_failures: list[tuple[UUID, str]]
    """Phase ID and error message for each automatic snapshot that failed."""
    blocking_items: int
    """Blocking readiness items of the events of the picks stored or updated.

    Not counted in a dry run.
    """
    dry_run: bool


def _events_of(session: Session, picks: Sequence[AimbatPick]) -> list[UUID]:
    """The events of picks, in order, for those whose event is known."""
    events: dict[UUID, None] = {}
    for pick in picks:
        if pick.seismogram_id is not None:
            seismogram = session.get_one(AimbatSeismogram, pick.seismogram_id)
            events[seismogram.event_id] = None
        elif pick.event_id is not None:
            events[pick.event_id] = None
    return list(events)


def add_picks(
    sources: Sequence[os.PathLike[str] | str],
    data_type: DataType = DataType.SAC,
    *,
    naming: PickNaming = PickNaming(),
    phases: Collection[str] | None = None,
    update: bool = False,
    dry_run: bool = False,
    auto_snapshot: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
    engine: Engine | None = None,
) -> AddPicksResult:
    """Read the picks of data sources already in the project, and store the new ones.

    Picks already stored are skipped. A stored pick whose time or label
    changed in its data source is counted, and updated with `update`. A
    promoted pick keeps its row, unless its new label gives it another phase
    name, in which case it moves to that phase. Dismissed picks are left as
    they are. New and updated picks that are named and matched are promoted.

    Args:
        sources: Data sources to read.
        data_type: Data type of the data sources.
        naming: How picks are named. See `aimbat.core.PickNaming`.
        phases: Names of the phases the call may create or add rows to.
            Every phase if `None`.
        update: Whether to apply the changed times and labels.
        dry_run: If True, report what would change without changing the
            project.
        auto_snapshot: If True, snapshot every phase that gains rows.
        on_progress: Callback invoked as `on_progress(done, total)` after
            each data source.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        FileNotFoundError: If a data source does not exist.
        ValueError: If `data_type` holds no picks, a data source is not in
            the project, a name in `phases` is not a valid phase name, or a
            pick is invalid. Nothing is changed.
    """
    with open_session(engine) as session:
        report = core.add_picks_to_project(
            session,
            sources,
            data_type,
            naming=naming,
            phases=phases,
            update=update,
            on_progress=on_progress,
        )
        picks = PickSummary.from_reports(
            report.stored, [], report.promotion, report.updated
        )
        names = [str(source) for source in sources]
        if dry_run:
            return AddPicksResult(names, picks, [], [], 0, dry_run=True)

        events = _events_of(session, [*report.stored.stored, *report.updated.updated])
        session.commit()
        blocking = sum(
            item.blocking
            for event_id in events
            for item in core.readiness(session, event_id=event_id, read_data=False)
        )
        snapshotted: list[UUID] = []
        failures: list[tuple[UUID, str]] = []
        if auto_snapshot:
            snapshotted, failures = core.create_snapshots_for_added_data(
                session, picks.phase_rows
            )
            session.commit()
    return AddPicksResult(names, picks, snapshotted, failures, blocking, dry_run=False)


@dataclass(frozen=True)
class PickChangeResult:
    """What an action that edits picks changed, or would change in a dry run."""

    picks: list[UUID] = field(default_factory=list)
    """Picks the action was applied to."""
    promoted: dict[str, int] = field(default_factory=dict)
    """Rows created, keyed by phase name."""
    phases_created: list[CreatedPhase] = field(default_factory=list)
    """Phases created."""
    conflicts: list[UUID] = field(default_factory=list)
    """Picks not promoted because the row holds a pick with another time."""
    invalid: list[UUID] = field(default_factory=list)
    """Picks not promoted because they fail the pick checks."""
    replaced: list[UUID] = field(default_factory=list)
    """Picks dismissed because another pick took over their row."""
    rows_deleted: int = 0
    """Rows deleted with the picks removed."""
    warnings: list[str] = field(default_factory=list)
    """Things to know about, which did not stop the change."""
    snapshotted_phase_ids: list[UUID] = field(default_factory=list)
    """Phases that gained rows and were snapshotted."""
    snapshot_failures: list[tuple[UUID, str]] = field(default_factory=list)
    """Phase ID and error message for each automatic snapshot that failed."""
    dry_run: bool = False
    """Whether the changes were discarded."""

    @property
    def total_promoted(self) -> int:
        """Number of rows created."""
        return sum(self.promoted.values())

    @classmethod
    def from_report(
        cls,
        pick_ids: Sequence[UUID],
        report: PromotionReport,
        *,
        dry_run: bool = False,
    ) -> "PickChangeResult":
        """Summarise a promotion report while its records are loaded."""
        return cls(
            picks=list(pick_ids),
            promoted=dict(Counter(row.phase.name for row in report.rows)),
            phases_created=_created_phases(report),
            conflicts=[p.id for p in report.conflicts],
            invalid=[p.id for p in report.invalid],
            replaced=[p.id for p in report.replaced],
            warnings=list(report.warnings),
            dry_run=dry_run,
        )


def _commit_promotion(
    session: Session,
    pick_ids: Sequence[UUID],
    report: PromotionReport,
    *,
    auto_snapshot: bool,
) -> PickChangeResult:
    """Commit a promotion, then snapshot each phase that gained rows."""
    result = PickChangeResult.from_report(pick_ids, report)
    phase_rows = Counter(row.phase_id for row in report.rows)
    session.commit()
    if not auto_snapshot:
        return result
    snapshotted, failures = core.create_snapshots_for_added_data(session, phase_rows)
    session.commit()
    return replace_fields(
        result, snapshotted_phase_ids=snapshotted, snapshot_failures=failures
    )


def name_picks(
    selection: PickSelection,
    phase_name: str,
    *,
    dry_run: bool = False,
    auto_snapshot: bool = True,
    engine: Engine | None = None,
) -> PickChangeResult:
    """Give the selected picks a phase name, and promote those that are matched.

    Phases missing for the picks are created.

    Args:
        selection: Picks to name. None of them may be promoted.
        phase_name: The phase name.
        dry_run: If True, report what would change without saving it.
        auto_snapshot: If True, snapshot every phase that gains rows.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If a pick the selection names does not exist.
        ValueError: If the selection has no criteria, the name is not a valid
            phase name, or a selected pick is promoted. Nothing is changed.
    """
    with open_session(engine) as session:
        picks = core.select_picks(session, selection)
        report = core.name_picks(session, picks, phase_name)
        pick_ids = [p.id for p in picks]
        if dry_run:
            result = PickChangeResult.from_report(pick_ids, report, dry_run=True)
            session.rollback()
            return result
        return _commit_promotion(session, pick_ids, report, auto_snapshot=auto_snapshot)


def promote_phase_picks(
    event_id: UUID | Literal["all"],
    phase_name: str,
    *,
    auto_snapshot: bool = True,
    engine: Engine | None = None,
) -> PickChangeResult:
    """Promote the matched picks named for a phase, creating the phase where missing.

    Args:
        event_id: ID of the event, or `"all"` for every event.
        phase_name: The phase name.
        auto_snapshot: If True, snapshot every phase that gains rows.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the event does not exist.
        ValueError: If the name is not a valid phase name.
    """
    with open_session(engine) as session:
        if event_id == "all":
            filter_id = None
        else:
            filter_id = core.resolve_event(session, event_id).id
        report = core.promote_phase_picks(session, phase_name, event_id=filter_id)
        return _commit_promotion(
            session,
            [row.pick_id for row in report.rows],
            report,
            auto_snapshot=auto_snapshot,
        )


def promote_picks(
    pick_ids: Sequence[UUID],
    *,
    replace: bool = False,
    auto_snapshot: bool = True,
    engine: Engine | None = None,
) -> PickChangeResult:
    """Promote the given picks, creating their phases where missing.

    Args:
        pick_ids: IDs of the picks.
        replace: Whether a pick takes over the row of its seismogram and
            phase when that row holds a pick with another time. The pick it
            replaces is dismissed.
        auto_snapshot: If True, snapshot every phase that gains rows. A
            replaced pick does not count as a gain.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If a pick does not exist.
        ValueError: If a pick is dismissed, unnamed or unmatched, or, with
            `replace`, two picks are for the same seismogram and phase.
            Nothing is changed.
    """
    with open_session(engine) as session:
        report = core.promote_existing_picks(session, pick_ids, replace_rows=replace)
        return _commit_promotion(
            session,
            list(dict.fromkeys(pick_ids)),
            report,
            auto_snapshot=auto_snapshot,
        )


def match_pick(
    pick_id: UUID,
    seismogram_id: UUID,
    *,
    auto_snapshot: bool = True,
    engine: Engine | None = None,
) -> PickChangeResult:
    """Match an unmatched pick to a seismogram of its event, and promote it if named.

    A missing phase is created. A station code the pick was read with that
    differs from the seismogram's is reported as a warning.

    Args:
        pick_id: ID of the pick.
        seismogram_id: ID of the seismogram.
        auto_snapshot: If True, snapshot the phase if it gains a row.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the pick or the seismogram does not exist.
        ValueError: If the pick is dismissed or already matched, its event is
            not the seismogram's, or it fails the pick checks for the
            seismogram. Nothing is changed.
    """
    with open_session(engine) as session:
        report = core.match_pick(session, pick_id, seismogram_id)
        return _commit_promotion(
            session, [pick_id], report, auto_snapshot=auto_snapshot
        )


def retry_pick_matching(
    event_id: UUID | Literal["all"] = "all",
    *,
    auto_snapshot: bool = True,
    engine: Engine | None = None,
) -> PickChangeResult:
    """Retry matching the unmatched picks read with a station code, and promote those matched.

    Covers the unmatched picks of the event (or of every event) and every
    pick whose event is not known. Phases missing for the picks are created.

    Args:
        event_id: ID of the event, or `"all"` for every event.
        auto_snapshot: If True, snapshot every phase that gains rows.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the event does not exist.
    """
    with open_session(engine) as session:
        if event_id == "all":
            filter_id = None
        else:
            filter_id = core.resolve_event(session, event_id).id
        matched, report = core.retry_pick_matching(session, event_id=filter_id)
        return _commit_promotion(
            session, [p.id for p in matched], report, auto_snapshot=auto_snapshot
        )


def set_initial_pick(
    seismogram_id: UUID,
    phase_name: str,
    time: Timestamp,
    *,
    replace: bool = False,
    engine: Engine | None = None,
) -> PickChangeResult:
    """Make a manual pick the initial pick of a seismogram for a phase.

    Not `set_picks`, which sets refined picks. The phase is created if it is
    missing. No snapshot is taken.

    Args:
        seismogram_id: ID of the seismogram.
        phase_name: The phase name.
        time: Time of the pick, with a time zone.
        replace: Whether to replace the pick of an existing row. The row
            keeps its other values, and the pick it held is dismissed.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the seismogram does not exist.
        ValueError: If the name is not a valid phase name, the time has no
            time zone or lies before the begin time of the seismogram, or the
            seismogram already has a row for the phase and `replace` is
            False. Nothing is changed.
    """
    with open_session(engine) as session:
        pick, report = core.set_initial_pick(
            session, seismogram_id, phase_name, time, replace_row=replace
        )
        result = PickChangeResult.from_report([pick.id], report)
        session.commit()
    return result


def remove_picks(
    selection: PickSelection, *, purge: bool = False, engine: Engine | None = None
) -> PickChangeResult:
    """Dismiss or delete the selected picks, and delete their rows.

    A dismissed pick is kept, and `restore_picks` undoes the dismissal. A
    deleted pick of a data source is stored again when the source is read
    again. With `purge`, dismissed picks are selected too. No snapshot is
    taken.

    Args:
        selection: Picks to remove.
        purge: Whether to delete the picks instead of dismissing them.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If a pick the selection names does not exist.
        ValueError: If the selection has no criteria, or, without `purge`, a
            pick it names is dismissed. Nothing is changed.
    """
    if purge:
        selection = replace_fields(selection, dismissed=None)
    with open_session(engine) as session:
        picks = core.select_picks(session, selection)
        report = core.remove_picks(session, picks, purge=purge)
        session.commit()
    return PickChangeResult(
        picks=report.purged if purge else report.dismissed,
        rows_deleted=report.rows_deleted,
    )


def restore_picks(
    selection: PickSelection,
    *,
    auto_snapshot: bool = True,
    engine: Engine | None = None,
) -> PickChangeResult:
    """Undo the dismissal of the selected picks, and promote those named and matched.

    Only dismissed picks are selected. Phases missing for the picks are
    created.

    Args:
        selection: Picks to restore.
        auto_snapshot: If True, snapshot every phase that gains rows.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If a pick the selection names does not exist.
        ValueError: If the selection has no criteria, or a pick it names is
            not dismissed. Nothing is changed.
    """
    selection = replace_fields(selection, dismissed=True)
    with open_session(engine) as session:
        picks = core.select_picks(session, selection)
        report = core.restore_picks(session, picks)
        return _commit_promotion(
            session, [p.id for p in picks], report, auto_snapshot=auto_snapshot
        )
