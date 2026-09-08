"""Reconcile an AIMBAT project with reality by pruning seismograms whose data source has vanished.

`prune_project` probes every data source in scope (see
`aimbat.io.source_present`), deletes the `AimbatSeismogram` rows whose source
can no longer be read, and repairs the fallout a plain delete leaves behind:
live ICCS/MCCC quality is re-nulled for every affected event (AIMBAT has no
`AFTER DELETE` triggers), emptied stations and events are optionally cleaned
up, and each affected event is snapshotted first.

Frozen snapshot history survives a prune untouched: a pruned seismogram's
`*Snapshot` rows keep their values and their own `seismogram_id`; only the
back-links to the deleted live rows go `NULL`.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from aimbat.io import (
    DataType,
    SourceUnavailableError,
    clear_seismogram_data_cache,
    source_present,
    supports_source_probe,
)
from aimbat.logger import logger
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatNote,
    AimbatSeismogram,
    AimbatSnapshot,
    AimbatStation,
)
from aimbat.utils import rel

__all__ = ["PruneReport", "prune_project"]


@dataclass
class PruneReport:
    """What `prune_project` found and (unless `dry_run`) did."""

    orphan_seismograms: list[AimbatSeismogram]
    """Seismograms whose data source probed absent."""
    orphan_sources: dict[UUID, tuple[str, DataType]]
    """Seismogram ID -> (sourcename, datatype) of the vanished source."""
    unprobeable: dict[DataType, int]
    """Datatype -> count of sources with no registered probe (reconcile incomplete)."""
    emptied_stations: list[AimbatStation]
    """Stations left with no seismograms once the orphans are gone."""
    emptied_events: list[AimbatEvent]
    """Events left with no seismograms; pruned only if `prune_empty_events`."""
    events_needing_invalidation: list[AimbatEvent]
    """Events that lose at least one seismogram and are not themselves pruned."""
    deleted_snapshots: dict[UUID, int]
    """Event ID -> number of snapshots destroyed by pruning that event."""
    cascaded_notes: dict[str, int]
    """"seismogram" | "station" | "event" -> count of notes cascade-deleted."""
    warnings: list[str]
    """Non-fatal warnings to surface to the user."""
    dry_run: bool
    pruned: bool = field(default=False)
    """True once the deletions have been committed."""

    @property
    def total_snapshots(self) -> int:
        """Total snapshots that will be, or were, destroyed."""
        return sum(self.deleted_snapshots.values())

    @property
    def total_notes(self) -> int:
        """Total notes that will be, or were, cascade-deleted."""
        return sum(self.cascaded_notes.values())


def _count_notes(session: Session, attr: str, ids: set[UUID]) -> int:
    """Count `AimbatNote` rows whose `<attr>` is in `ids`."""
    if not ids:
        return 0
    return session.exec(
        select(func.count(col(AimbatNote.id))).where(
            col(getattr(AimbatNote, attr)).in_(ids)
        )
    ).one()


def prune_project(
    session: Session,
    event_id: UUID | Literal["all"],
    *,
    dry_run: bool = False,
    prune_empty_stations: bool = False,
    prune_empty_events: bool = False,
    auto_snapshot: bool = True,
    force: bool = False,
    confirm: Callable[[PruneReport], bool] | None = None,
) -> PruneReport:
    """Delete seismograms whose data source can no longer be read.

    Args:
        session: Database session.
        event_id: A single event's ID, or the literal `"all"` for the whole
            project. Mirrors `aimbat data list`.
        dry_run: Probe and report only; delete nothing.
        prune_empty_stations: Also delete stations left with no seismograms.
        prune_empty_events: Also delete events left with no seismograms.
            Deleting an event irreversibly destroys its snapshot history.
        auto_snapshot: Snapshot every affected event before deleting anything.
            A snapshot failure aborts the prune with nothing deleted.
        force: Treat a source whose presence cannot be determined (an
            unreadable file, a missing parent directory, an unreachable mount)
            as vanished instead of stopping. Without it, such a source is a
            hard error and nothing is pruned.
        confirm: Optional callback invoked once with the completed
            `PruneReport` after probing but before any deletion (skipped on a
            `dry_run` or when nothing is orphaned). Return `False` to abort
            with nothing deleted; the same probe results are then used for the
            deletion, so the user acts on exactly what was reported.

    Returns:
        A `PruneReport`.

    Raises:
        NoResultFound: If `event_id` is not `"all"` and names no event.
        SourceUnavailableError: If a source's presence cannot be determined
            and `force` is not set; nothing is pruned.
        RuntimeError: If `auto_snapshot` is set and an affected event cannot
            be snapshotted; nothing is pruned.
    """
    all_scope = isinstance(event_id, str) and event_id.lower() == "all"
    if not all_scope and session.get(AimbatEvent, event_id) is None:
        raise NoResultFound(f"No AimbatEvent found with id: {event_id}.")
    scope_label = "all events" if all_scope else f"event {event_id}"
    logger.info(f"Pruning {scope_label} (dry_run={dry_run}).")

    # A column query, not an ORM-object one: holding `AimbatDataSource`
    # instances in the session would make `session.delete(seismogram)` issue a
    # redundant ORM DELETE for a row the DB-level `ON DELETE CASCADE` already
    # removes.
    source_stmt = select(
        AimbatDataSource.sourcename,
        AimbatDataSource.datatype,
        AimbatDataSource.seismogram_id,
    ).join(AimbatSeismogram)
    if not all_scope:
        source_stmt = source_stmt.where(AimbatSeismogram.event_id == event_id)
    source_rows = session.exec(source_stmt).all()

    warnings: list[str] = []
    orphan_sources: dict[UUID, tuple[str, DataType]] = {}
    unprobeable: dict[DataType, int] = {}
    for sourcename, datatype_raw, seismogram_id in source_rows:
        sourcename = str(sourcename)
        datatype = DataType(datatype_raw)
        if not supports_source_probe(datatype):
            unprobeable[datatype] = unprobeable.get(datatype, 0) + 1
            continue
        try:
            present = source_present(sourcename, datatype, session)
        except SourceUnavailableError as exc:
            if not force:
                raise SourceUnavailableError(
                    f"Cannot determine whether data source {sourcename!r} "
                    + f"({datatype}) is present: {exc} Nothing was pruned. "
                    + "Restore the path, or re-run with force if these data "
                    + "are gone for good."
                ) from exc
            warnings.append(
                f"force: treating {sourcename!r} ({datatype}) as vanished "
                + f"even though its absence could not be confirmed ({exc})."
            )
            present = False
        if not present:
            orphan_sources[seismogram_id] = (sourcename, datatype)

    orphan_ids = set(orphan_sources)
    orphan_seismograms: list[AimbatSeismogram] = []
    if orphan_ids:
        orphan_seismograms = list(
            session.exec(
                select(AimbatSeismogram)
                .where(col(AimbatSeismogram.id).in_(orphan_ids))
                .options(
                    selectinload(rel(AimbatSeismogram.station)),
                    selectinload(rel(AimbatSeismogram.event)),
                )
            ).all()
        )

    affected_event_ids = {s.event_id for s in orphan_seismograms}
    affected_station_ids = {s.station_id for s in orphan_seismograms}

    events: list[AimbatEvent] = []
    if affected_event_ids:
        events = list(
            session.exec(
                select(AimbatEvent)
                .where(col(AimbatEvent.id).in_(affected_event_ids))
                .options(selectinload(rel(AimbatEvent.seismograms)))
            ).all()
        )
    stations: list[AimbatStation] = []
    if affected_station_ids:
        stations = list(
            session.exec(
                select(AimbatStation)
                .where(col(AimbatStation.id).in_(affected_station_ids))
                .options(selectinload(rel(AimbatStation.seismograms)))
            ).all()
        )

    emptied_events = [
        e for e in events if all(s.id in orphan_ids for s in e.seismograms)
    ]
    emptied_event_ids = {e.id for e in emptied_events}
    emptied_stations = [
        st for st in stations if all(s.id in orphan_ids for s in st.seismograms)
    ]

    pruned_event_ids = emptied_event_ids if prune_empty_events else set()
    events_needing_invalidation = [e for e in events if e.id not in pruned_event_ids]

    deleted_snapshots: dict[UUID, int] = {}
    if prune_empty_events:
        for e in emptied_events:
            count = session.exec(
                select(func.count(col(AimbatSnapshot.id))).where(
                    col(AimbatSnapshot.event_id) == e.id
                )
            ).one()
            if count:
                deleted_snapshots[e.id] = count

    cascaded_notes: dict[str, int] = {}
    seismogram_notes = _count_notes(session, "seismogram_id", orphan_ids)
    if seismogram_notes:
        cascaded_notes["seismogram"] = seismogram_notes
    if prune_empty_stations:
        station_notes = _count_notes(
            session, "station_id", {st.id for st in emptied_stations}
        )
        if station_notes:
            cascaded_notes["station"] = station_notes
    if prune_empty_events:
        event_notes = _count_notes(session, "event_id", emptied_event_ids)
        if event_notes:
            cascaded_notes["event"] = event_notes

    for datatype, count in unprobeable.items():
        warnings.append(
            f"Could not check {count} {datatype} source(s); reconcile incomplete."
        )

    report = PruneReport(
        orphan_seismograms=orphan_seismograms,
        orphan_sources=orphan_sources,
        unprobeable=unprobeable,
        emptied_stations=emptied_stations,
        emptied_events=emptied_events,
        events_needing_invalidation=events_needing_invalidation,
        deleted_snapshots=deleted_snapshots,
        cascaded_notes=cascaded_notes,
        warnings=warnings,
        dry_run=dry_run,
    )

    if dry_run or not orphan_seismograms:
        return report

    if confirm is not None and not confirm(report):
        logger.info("Prune cancelled before any deletion.")
        return report

    from ._iccs import _invalidate_event_quality, clear_iccs_cache
    from ._snapshot import create_snapshot

    invalidate_event_ids = [e.id for e in events_needing_invalidation]
    prune_station_ids = [s.id for s in emptied_stations] if prune_empty_stations else []
    prune_event_ids = [e.id for e in emptied_events] if prune_empty_events else []

    # Detach the eagerly loaded report graph now, while its relationships are
    # still populated. `create_snapshot` commits (expiring every attached
    # instance) and every deletion below reloads its target by ID, so nothing
    # past this point needs these instances bound to the session - but callers
    # still read `report.orphan_seismograms[*].station` and friends afterwards.
    session.expunge_all()

    if auto_snapshot:
        for event_uuid in invalidate_event_ids:
            snap_event = session.get(AimbatEvent, event_uuid)
            if snap_event is None:
                continue
            try:
                create_snapshot(
                    session,
                    snap_event,
                    comment="Automatic snapshot before prune",
                    automatic=True,
                )
            except Exception as exc:
                session.rollback()
                raise RuntimeError(
                    f"Aborting prune: could not snapshot event {event_uuid} "
                    + f"first ({exc}). Nothing was deleted."
                ) from exc

    for event_uuid in invalidate_event_ids:
        _invalidate_event_quality(session, event_uuid)

    # Every deletion below reloads its target by ID with no relationships
    # attached, so `session.delete()` leaves the 1:1 children (data source,
    # parameters, quality) to the DB-level `ON DELETE CASCADE` instead of also
    # issuing a redundant ORM DELETE for each - matching `core.delete_seismogram`.
    for seismogram_uuid in orphan_ids:
        seismogram = session.get(AimbatSeismogram, seismogram_uuid)
        if seismogram is not None:
            session.delete(seismogram)
    session.flush()
    for station_uuid in prune_station_ids:
        station = session.get(AimbatStation, station_uuid)
        if station is not None:
            session.delete(station)
    for event_uuid in prune_event_ids:
        event = session.get(AimbatEvent, event_uuid)
        if event is not None:
            session.delete(event)
    session.commit()

    clear_seismogram_data_cache()
    clear_iccs_cache()

    report.pruned = True
    pruned_stations = len(emptied_stations) if prune_empty_stations else 0
    pruned_events = len(emptied_events) if prune_empty_events else 0
    logger.info(
        f"Pruned {len(orphan_seismograms)} seismogram(s), "
        + f"{pruned_stations} station(s), {pruned_events} event(s)."
    )
    return report
