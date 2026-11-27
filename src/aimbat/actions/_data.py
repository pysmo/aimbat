"""Actions that add data sources to a project or remove vanished ones."""

import os
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pandas import Timestamp
from sqlalchemy import Engine

from aimbat import core
from aimbat.core import PickNaming, PruneReport
from aimbat.io import DataType

from ._picks import PickSummary
from ._readiness import ReadinessCounts, _count_items
from ._session import open_session

__all__ = [
    "AddDataResult",
    "AddedDataSource",
    "OrphanSeismogram",
    "PruneResult",
    "add_data",
    "prune_data",
]


@dataclass(frozen=True)
class AddedDataSource:
    """A data source processed by `add_data`, with the records it is linked to."""

    sourcename: str
    station_id: UUID
    event_id: UUID
    seismogram_id: UUID
    new_station: bool
    """True if the station was created by this call."""
    new_event: bool
    """True if the event was created by this call."""
    new_seismogram: bool
    """True if the seismogram was created by this call."""


@dataclass(frozen=True)
class AddDataResult:
    """Outcome of `add_data`, or of a dry run."""

    sources: list[AddedDataSource]
    """All data sources processed, whether newly added or already present."""
    duplicate_warnings: list[str]
    """Messages about near-duplicate events merged onto existing ones.

    Populated in dry runs only.
    """
    picks: PickSummary
    """What became of the picks read from the data sources."""
    snapshotted_phase_ids: list[UUID]
    """Phases that gained rows and were snapshotted."""
    snapshot_failures: list[tuple[UUID, str]]
    """Phase ID and error message for each automatic snapshot that failed."""
    readiness: ReadinessCounts
    """Readiness items of the events the data sources belong to.

    Not counted in a dry run. Initial picks are not checked against the end
    of their seismogram here (see `aimbat.core.readiness`).
    """
    dry_run: bool


def add_data(
    data_sources: Sequence[os.PathLike[str] | str],
    data_type: DataType,
    *,
    station_id: UUID | None = None,
    event_id: UUID | None = None,
    naming: PickNaming = PickNaming(),
    phases: Collection[str] | None = None,
    dry_run: bool = False,
    auto_snapshot: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
    engine: Engine | None = None,
) -> AddDataResult:
    """Add data sources to the project.

    Data sources that are already part of the project are reused rather than
    duplicated. Picks read from the data sources are stored and, when named,
    promoted to initial picks of the phase of that name. Picks stored earlier
    without a matching seismogram are matched again.

    Args:
        data_sources: Data sources to add.
        data_type: Data type of the data sources.
        station_id: Existing station to link every data source to, instead
            of the station read from each source.
        event_id: Existing event to link every data source to, instead of
            the event read from each source.
        naming: How picks are named. See `aimbat.core.PickNaming`.
        phases: Names of the phases the call may create or add rows to.
            Every phase if `None`.
        dry_run: If True, report what would be added without changing the
            project.
        auto_snapshot: If True, snapshot every phase that gains rows.
        on_progress: Callback invoked as `on_progress(done, total)` after
            each data source.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        FileNotFoundError: If a data source does not exist.
        ValueError: If a new event nearly, but not exactly, matches an
            existing one (see `aimbat.core.add_data_to_project`), or a name
            in `phases` is not a valid phase name.
    """
    with open_session(engine) as session:
        report = core.add_data_to_project(
            session,
            data_sources,
            data_type,
            station_id=station_id,
            event_id=event_id,
            dry_run=dry_run,
            on_progress=on_progress,
            naming=naming,
            phases=phases,
        )
        sources = [
            AddedDataSource(
                sourcename=str(ds.sourcename),
                station_id=ds.seismogram.station_id,
                event_id=ds.seismogram.event_id,
                seismogram_id=ds.seismogram_id,
                new_station=ds.seismogram.station_id not in report.existing_station_ids,
                new_event=ds.seismogram.event_id not in report.existing_event_ids,
                new_seismogram=ds.seismogram_id not in report.existing_seismogram_ids,
            )
            for ds in report.datasources
        ]
        picks = PickSummary.from_reports(
            report.stored, report.rematched, report.promotion
        )
        warnings = report.duplicate_warnings
        if dry_run:
            return AddDataResult(
                sources, warnings, picks, [], [], ReadinessCounts(), dry_run=True
            )

        session.commit()
        counts = _count_items(session, (s.event_id for s in sources))
        snapshotted: list[UUID] = []
        failures: list[tuple[UUID, str]] = []
        if auto_snapshot:
            snapshotted, failures = core.create_snapshots_for_added_data(
                session, picks.phase_rows
            )
            session.commit()
    return AddDataResult(
        sources, warnings, picks, snapshotted, failures, counts, dry_run=False
    )


@dataclass(frozen=True)
class OrphanSeismogram:
    """A seismogram whose data source can no longer be read."""

    seismogram_id: UUID
    sourcename: str
    datatype: DataType
    station_name: str
    event_time: Timestamp


@dataclass(frozen=True)
class PruneResult:
    """Outcome of `prune_data`, or of a dry run."""

    orphans: list[OrphanSeismogram]
    """Seismograms whose data sources can no longer be read."""
    unprobeable: dict[DataType, int]
    """Number of data sources that could not be checked, keyed by data type."""
    emptied_station_ids: list[UUID]
    """Stations left without seismograms once the orphans are removed."""
    emptied_event_ids: list[UUID]
    """Events left without seismograms once the orphans are removed."""
    events_losing_seismograms: dict[UUID, Timestamp]
    """Origin time of each event that loses seismograms but is kept, keyed by
    event ID."""
    deleted_snapshots: dict[UUID, int]
    """Number of snapshots deleted with each event, keyed by event ID."""
    cascaded_notes: dict[str, int]
    """Number of notes deleted, keyed by record type (`"seismogram"`,
    `"station"` or `"event"`)."""
    warnings: list[str]
    dry_run: bool
    pruned: bool
    """True once the deletions have been committed."""

    @property
    def total_snapshots(self) -> int:
        """Total number of snapshots deleted, or to be deleted."""
        return sum(self.deleted_snapshots.values())

    @property
    def total_notes(self) -> int:
        """Total number of notes deleted, or to be deleted."""
        return sum(self.cascaded_notes.values())

    @classmethod
    def from_report(cls, report: PruneReport) -> "PruneResult":
        """Build a result from a `PruneReport` while its records are loaded."""
        return cls(
            orphans=[
                OrphanSeismogram(
                    seismogram_id=seis.id,
                    sourcename=report.orphan_sources[seis.id][0],
                    datatype=report.orphan_sources[seis.id][1],
                    station_name=seis.station.name,
                    event_time=seis.event.time,
                )
                for seis in report.orphan_seismograms
            ],
            unprobeable=dict(report.unprobeable),
            emptied_station_ids=[s.id for s in report.emptied_stations],
            emptied_event_ids=[e.id for e in report.emptied_events],
            events_losing_seismograms={
                e.id: e.time for e in report.events_losing_seismograms
            },
            deleted_snapshots=dict(report.deleted_snapshots),
            cascaded_notes=dict(report.cascaded_notes),
            warnings=list(report.warnings),
            dry_run=report.dry_run,
            pruned=report.pruned,
        )


def prune_data(
    event_id: UUID | Literal["all"],
    *,
    dry_run: bool = False,
    prune_empty_stations: bool = False,
    prune_empty_events: bool = False,
    auto_snapshot: bool = True,
    force: bool = False,
    confirm: Callable[[PruneResult], bool] | None = None,
    engine: Engine | None = None,
) -> PruneResult:
    """Delete seismograms whose data source can no longer be read.

    Args:
        event_id: Event to check, or `"all"` for every event.
        dry_run: If True, report what would be deleted without deleting
            anything.
        prune_empty_stations: If True, also delete stations left without
            seismograms.
        prune_empty_events: If True, also delete events left without
            seismograms.
        auto_snapshot: If True, snapshot every phase that loses rows before
            deleting anything.
        force: If True, treat a data source whose presence cannot be
            determined (an unreadable file, an unreachable mount) as
            vanished. Otherwise such a source is an error and nothing is
            deleted.
        confirm: Callback that receives the pending deletions before any is
            made. Deletion proceeds only if it returns True. It is not called
            for a dry run or when there is nothing to delete.
        engine: Engine to use. Defaults to the project engine.
    """
    core_confirm = (
        None
        if confirm is None
        else lambda report: confirm(PruneResult.from_report(report))
    )
    with open_session(engine) as session:
        report = core.prune_project(
            session,
            event_id,
            dry_run=dry_run,
            prune_empty_stations=prune_empty_stations,
            prune_empty_events=prune_empty_events,
            auto_snapshot=auto_snapshot,
            force=force,
            confirm=core_confirm,
        )
        result = PruneResult.from_report(report)
        if not dry_run:
            session.commit()
    return result
