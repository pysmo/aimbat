"""Add data sources to an AIMBAT project, creating and linking station, event, and seismogram records."""

import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

from pandas import Timedelta
from pydantic import TypeAdapter
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from pysmo import Event, MiniStationCode, Station
from pysmo.lib.io import write_mseed
from pysmo.tools.iccs import IccsSeismogram

from aimbat import settings
from aimbat.io import (
    DataType,
    create_event,
    create_seismogram,
    create_station,
    supports_event_creation,
    supports_seismogram_creation,
    supports_station_creation,
)
from aimbat.logger import logger
from aimbat.models._models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatEventParameters,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
    _AimbatDataSourceCreate,
)
from aimbat.utils import get_title_map
from aimbat.utils.formatters import fmt_timedelta

__all__ = [
    "add_data_to_project",
    "add_seismograms_to_project",
    "get_data_for_event",
    "dump_data_table",
]


def _link_station(session: Session, new_aimbat_station: AimbatStation) -> AimbatStation:
    """Dedup an already-built AimbatStation against the project, or add it."""

    statement = (
        select(AimbatStation)
        .where(AimbatStation.name == new_aimbat_station.name)
        .where(AimbatStation.network == new_aimbat_station.network)
        .where(AimbatStation.channel == new_aimbat_station.channel)
        .where(AimbatStation.location == new_aimbat_station.location)
    )
    aimbat_station = session.exec(statement).one_or_none()

    if aimbat_station is None:
        aimbat_station = new_aimbat_station
        logger.debug(
            f"Adding station {aimbat_station.name} - {aimbat_station.network} to project."
        )
        session.add(aimbat_station)
    else:
        logger.debug(
            f"Using existing station {aimbat_station.name} - {aimbat_station.network} instead of adding new one."
        )
    return aimbat_station


def _create_station(
    session: Session, datasource: os.PathLike[str] | str, datatype: DataType
) -> AimbatStation:
    """Create a new AimbatStation if it doesn't exist yet, or use existing one."""

    new_aimbat_station = create_station(datasource, datatype)
    return _link_station(session, new_aimbat_station)


def _format_gap_prefix(
    label: str,
    new_event: AimbatEvent,
    existing_event: AimbatEvent,
    gap: Timedelta,
) -> str:
    """Build the shared origin-time/gap/existing-event sentence fragment."""
    return (
        f"{label} has origin time {new_event.time}, "
        f"{fmt_timedelta(gap)} from existing event {existing_event.id} "
        f"({existing_event.time})"
    )


def _format_reused_near_duplicate_message(
    label: str,
    new_event: AimbatEvent,
    existing_event: AimbatEvent,
    gap: Timedelta,
    tolerance: Timedelta,
) -> str:
    """Build the noise-band near-duplicate-event reuse message."""
    prefix = _format_gap_prefix(label, new_event, existing_event, gap)
    return (
        f"Near-duplicate event: {prefix}, within the configured "
        f"duplicate-detection tolerance ({fmt_timedelta(tolerance)}) but "
        f"not an exact match. Reusing the existing event; its stored time "
        f"and location are kept unchanged. Set 'event_duplicate_strict' to "
        f"treat close origin times as genuinely distinct events instead."
    )


def _warn_on_event_location_mismatch(
    label: str,
    new_event: AimbatEvent,
    existing_event: AimbatEvent,
) -> None:
    """Warn if the reused event's location metadata differs from the source's."""
    if (
        new_event.latitude != existing_event.latitude
        or new_event.longitude != existing_event.longitude
        or new_event.depth != existing_event.depth
    ):
        logger.warning(
            f"Event at {existing_event.time} matched by time but has different "
            f"location metadata in {label}. The existing record will be used."
        )


def _format_ambiguous_gap_message(
    label: str,
    new_event: AimbatEvent,
    existing_event: AimbatEvent,
    gap: Timedelta,
    tolerance: Timedelta,
    raise_tolerance: Timedelta,
) -> str:
    """Build the ambiguous-gap-band event-time-conflict message."""
    prefix = _format_gap_prefix(label, new_event, existing_event, gap)
    return (
        f"Event time conflict: {prefix}, too large a gap to be explained "
        f"by ordinary timestamp precision noise (tolerance "
        f"{fmt_timedelta(tolerance)}) but too small to confidently treat as "
        f"an unrelated event (raise threshold {fmt_timedelta(raise_tolerance)}"
        f"). This usually indicates a timing problem in the source data; "
        f"check it before importing. If these are known to be genuinely "
        f"distinct events, set 'event_duplicate_strict' to skip this check."
    )


def _link_event(
    session: Session,
    new_aimbat_event: AimbatEvent,
    dry_run: bool,
    known_event_ids: set[UUID],
    label: str,
) -> tuple[AimbatEvent, str | None]:
    """Dedup an already-built AimbatEvent against the project, or add it.

    If no exact time match is found, checks whether the new event's origin
    time is a near-duplicate of a known event's time, per
    `settings.event_duplicate_tolerance` / `event_duplicate_raise_tolerance`
    / `event_duplicate_strict` (see the `data add` module docstring for the
    three-tier model). Within `event_duplicate_tolerance` the existing event
    is reused (with a warning), exactly as an exact-time match is.
    `known_event_ids` is updated in place with the ID of any newly created
    event, so later entries in the same batch are checked against events
    created earlier in that batch too. `label` identifies `new_aimbat_event`
    in log/warning messages (a data source path, or e.g. a
    `f"{network}.{station}"` for an object-based entry with no path).

    Raises:
        ValueError: If a near-duplicate (regardless of `dry_run`) falls in
            the wider "ambiguous gap" band between
            `event_duplicate_tolerance` and
            `event_duplicate_raise_tolerance`.
    """

    statement = select(AimbatEvent).where(AimbatEvent.time == new_aimbat_event.time)
    aimbat_event = session.exec(statement).one_or_none()

    if aimbat_event is None:
        if not settings.event_duplicate_strict:
            tolerance = settings.event_duplicate_tolerance
            raise_tolerance = settings.event_duplicate_raise_tolerance
            near_statement = select(AimbatEvent).where(
                AimbatEvent.time.between(  # type: ignore[attr-defined]
                    new_aimbat_event.time - raise_tolerance,
                    new_aimbat_event.time + raise_tolerance,
                ),
            )
            near_duplicates = [
                e for e in session.exec(near_statement).all() if e.id in known_event_ids
            ]
            if near_duplicates:
                closest = min(
                    near_duplicates, key=lambda e: abs(e.time - new_aimbat_event.time)
                )
                gap = abs(closest.time - new_aimbat_event.time)
                # Strictly less than raise_tolerance: at or beyond it, the
                # gap is treated as fully independent (see the setting's
                # "closer than this value" description in _config.py).
                if gap < raise_tolerance:
                    if gap <= tolerance:
                        message = _format_reused_near_duplicate_message(
                            label, new_aimbat_event, closest, gap, tolerance
                        )
                        logger.warning(message)
                        _warn_on_event_location_mismatch(
                            label, new_aimbat_event, closest
                        )
                        return closest, message if dry_run else None
                    raise ValueError(
                        _format_ambiguous_gap_message(
                            label,
                            new_aimbat_event,
                            closest,
                            gap,
                            tolerance,
                            raise_tolerance,
                        )
                    )
        aimbat_event = new_aimbat_event
        logger.debug(f"Adding event {aimbat_event.time} to project.")
        session.add(aimbat_event)
        known_event_ids.add(aimbat_event.id)
    else:
        logger.debug(
            f"Using existing event {aimbat_event.time} instead of adding new one."
        )
        _warn_on_event_location_mismatch(label, new_aimbat_event, aimbat_event)

    return aimbat_event, None


def _create_event(
    session: Session,
    datasource: os.PathLike[str] | str,
    datatype: DataType,
    dry_run: bool,
    known_event_ids: set[UUID],
) -> tuple[AimbatEvent, str | None]:
    """Create a new AimbatEvent if it doesn't exist yet, or use existing one."""

    new_aimbat_event = create_event(datasource, datatype)
    return _link_event(
        session, new_aimbat_event, dry_run, known_event_ids, str(datasource)
    )


def _format_seismogram_collision_message(label: str, sourcename: str) -> str:
    """Build the message for a seismogram whose deterministic path collides with an already-ingested one."""
    return (
        f"Seismogram collision for {label}: {sourcename} was already "
        f"persisted by an earlier ingest. Keeping the existing waveform and "
        f"database row; this triple's data was not written."
    )


def _link_seismogram(
    session: Session, new_aimbat_seismogram: AimbatSeismogram, sourcename: str
) -> AimbatSeismogram:
    """Dedup an already-built AimbatSeismogram against the project, or add it."""

    statement = (
        select(AimbatSeismogram)
        .join(AimbatDataSource)
        .where(AimbatDataSource.sourcename == sourcename)
    )

    aimbat_seismogram = session.exec(statement).one_or_none()
    if aimbat_seismogram is None:
        logger.debug(f"Adding seismogram with data source {sourcename} to project.")
        aimbat_seismogram = new_aimbat_seismogram
        session.add(aimbat_seismogram)
    else:
        logger.debug(
            f"Using existing seismogram with data source {sourcename} instead of adding new one."
        )
    return aimbat_seismogram


def _create_seismogram(
    session: Session, datasource: os.PathLike[str] | str, datatype: DataType
) -> AimbatSeismogram:
    """Create a new AimbatSeismogram if it doesn't exist yet, or use existing one."""

    new_aimbat_seismogram = create_seismogram(datasource, datatype)
    return _link_seismogram(session, new_aimbat_seismogram, str(datasource))


def _link_datasource(
    session: Session,
    sourcename: str,
    datatype: DataType,
    aimbat_seismogram: AimbatSeismogram,
) -> AimbatDataSource:
    """Dedup an AimbatDataSource by sourcename, or add one linking to `aimbat_seismogram`."""

    statement = select(AimbatDataSource).where(
        AimbatDataSource.sourcename == sourcename
    )
    aimbat_data_source = session.exec(statement).one_or_none()
    if aimbat_data_source is None:
        logger.debug(f"Adding data source {sourcename} to project.")
        aimbat_data_source = AimbatDataSource.model_validate(
            _AimbatDataSourceCreate(sourcename=sourcename, datatype=datatype),
            update={"seismogram": aimbat_seismogram},
        )
    else:
        logger.debug(
            f"Using existing data source {sourcename} instead of adding new one."
        )
        aimbat_data_source.seismogram = aimbat_seismogram
    session.add(aimbat_data_source)
    return aimbat_data_source


def _process_datasource(
    session: Session,
    datasource: os.PathLike[str] | str,
    datatype: DataType,
    station_id: UUID | None,
    event_id: UUID | None,
    dry_run: bool,
    known_event_ids: set[UUID],
) -> tuple[AimbatDataSource | None, str | None]:
    """Process a single data source, creating whichever entities the data type supports.

    Returns an `AimbatDataSource` when seismogram data are created, or `None`
    for station-only or event-only imports.

    Args:
        session: Database session.
        datasource: Path or identifier of the data source to process.
        datatype: Type of data, which determines which of station, event, and
            seismogram creation are attempted.
        station_id: UUID of an existing station to link to instead of
            extracting one from `datasource`.
        event_id: UUID of an existing event to link to instead of extracting
            one from `datasource`.
        dry_run: If True, a near-duplicate event within
            `settings.event_duplicate_tolerance` is surfaced as a preview
            warning message (in addition to the log warning a real add
            also emits).
        known_event_ids: IDs of events eligible for near-duplicate matching;
            updated in place as new events are created, so later data sources
            in the same batch are checked against earlier ones too.

    Returns:
        A 2-tuple of the created or reused `AimbatDataSource` (or `None` if
        `datatype` does not support seismogram creation) and a near-duplicate
        warning message for a dry run (or `None` if not a dry run, no
        near-duplicate was found, or the one found was outside
        `settings.event_duplicate_tolerance`).

    Raises:
        ValueError: If `event_id` is given but no matching event exists, if
            `datatype` does not support the station or event creation
            required to link a seismogram, or if a near-duplicate event
            falls in the "ambiguous gap" band between
            `settings.event_duplicate_tolerance` and
            `settings.event_duplicate_raise_tolerance` (raised regardless of
            `dry_run`).
    """

    duplicate_warning: str | None = None

    # Resolve station: use the provided UUID, extract from the source, or skip
    if station_id is not None:
        aimbat_station: AimbatStation | None = session.get(AimbatStation, station_id)
        if aimbat_station is None:
            raise ValueError(f"No station found with ID={station_id}.")
        logger.debug(
            f"Using station {getattr(aimbat_station, 'name', 'Unknown')} - {getattr(aimbat_station, 'network', 'Unknown')} (ID={station_id})."
        )
    elif supports_station_creation(datatype):
        aimbat_station = _create_station(session, datasource, datatype)
    else:
        aimbat_station = None

    # Resolve event: use the provided UUID, extract from the source, or skip
    if event_id is not None:
        aimbat_event: AimbatEvent | None = session.get(AimbatEvent, event_id)
        if aimbat_event is None:
            raise ValueError(f"No event found with ID={event_id}.")
        logger.debug(f"Using event {aimbat_event.time} (ID={event_id}).")
    elif supports_event_creation(datatype):
        aimbat_event, duplicate_warning = _create_event(
            session, datasource, datatype, dry_run, known_event_ids
        )
    else:
        aimbat_event = None

    # No seismogram creation → station/event-only import, nothing more to do
    if not supports_seismogram_creation(datatype):
        return None, duplicate_warning

    # Seismogram creation requires both a station and an event to link to
    if aimbat_station is None:
        raise ValueError(
            f"{datatype} does not support station creation. "
            "Provide a station UUID via --use-station."
        )
    if aimbat_event is None:
        raise ValueError(
            f"{datatype} does not support event creation. "
            "Provide an event UUID via --use-event."
        )

    aimbat_seismogram = _create_seismogram(session, datasource, datatype)
    # TODO: perhaps updating station/event info from the source should be optional
    aimbat_seismogram.station = aimbat_station
    aimbat_seismogram.event = aimbat_event

    logger.debug(
        f"Linking seismogram from {datasource} to "
        f"Station={aimbat_station.name} and EventTime={aimbat_event.time}."
    )

    aimbat_data_source = _link_datasource(
        session, str(datasource), datatype, aimbat_seismogram
    )
    return aimbat_data_source, duplicate_warning


def add_data_to_project(
    session: Session,
    data_sources: Sequence[os.PathLike[str] | str],
    data_type: DataType,
    station_id: UUID | None = None,
    event_id: UUID | None = None,
    dry_run: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[AimbatDataSource], set[UUID], set[UUID], set[UUID], list[str]]:
    """Add data sources to the AIMBAT database.

    What gets created depends on which capabilities `data_type` supports:

    - Station + event + seismogram: all three records are created and linked,
      and an `AimbatDataSource` entry is stored.
    - Station or event only (e.g. `JSON_STATION`, `JSON_EVENT`): only the
      relevant metadata records are created; no seismogram or data source entry
      is stored.

    Use `station_id` or `event_id` to skip extracting station or event metadata
    from the data source and link to a pre-existing record instead.

    A new event whose origin time nearly, but not exactly, matches a
    pre-existing event's time is handled per
    `settings.event_duplicate_tolerance`, `event_duplicate_raise_tolerance`,
    and `event_duplicate_strict`. Within the tighter tolerance the existing
    event is reused, with a log warning (a dry run additionally returns the
    message in `duplicate_warnings`). Within the wider "ambiguous gap" band,
    a `ValueError` is raised unconditionally, even during a dry run.

    Args:
        session: The SQLModel database session.
        data_sources: List of data sources to add.
        data_type: Type of data.
        station_id: UUID of an existing station to use instead of extracting
            one from each data source.
        event_id: UUID of an existing event to use instead of extracting one
            from each data source.
        dry_run: If True, do not commit changes to the database.
        on_progress: Optional callback invoked as `on_progress(done, total)`
            after each data source is processed, for callers that want to
            display progress.

    Returns:
        A 5-tuple of `(added_datasources, existing_station_ids,
        existing_event_ids, existing_seismogram_ids, duplicate_warnings)`.
        `added_datasources` is every `AimbatDataSource` touched by this call,
        new or reused. `existing_*_ids` are the sets of station/event/
        seismogram IDs that already existed in the database *before* this
        call, so callers can tell which entries in `added_datasources` are
        newly created versus reused by comparing IDs against these sets.
        `duplicate_warnings` lists near-duplicate-event reuse messages
        collected during a dry run (always empty on a real-add call, which
        logs the same message as a warning instead).

    Raises:
        ValueError: If a near-duplicate event falls in the "ambiguous gap"
            band (see above).
    """

    logger.info(f"Adding {len(data_sources)} {data_type} data sources to project.")

    if station_id is not None and session.get(AimbatStation, station_id) is None:
        raise NoResultFound(f"No station found with ID {station_id}.")
    if event_id is not None and session.get(AimbatEvent, event_id) is None:
        raise NoResultFound(f"No event found with ID {event_id}.")

    # Snapshot existing IDs before entering the savepoint so we can identify
    # what is new vs reused, for a dry run or otherwise.
    existing_station_ids = set(session.exec(select(AimbatStation.id)).all())
    existing_event_ids = set(session.exec(select(AimbatEvent.id)).all())
    existing_seismogram_ids = set(session.exec(select(AimbatSeismogram.id)).all())

    # Mutated in place as new events are created, so near-duplicate
    # detection also covers events created earlier in this same batch,
    # unlike existing_event_ids, which stays a frozen pre-batch snapshot
    # for the return value's new-vs-reused semantics.
    known_event_ids = set(existing_event_ids)

    try:
        added_datasources: list[AimbatDataSource] = []
        duplicate_warnings: list[str] = []
        total = len(data_sources)
        with session.begin_nested() as nested:
            for done, datasource in enumerate(data_sources, start=1):
                result, duplicate_warning = _process_datasource(
                    session,
                    datasource,
                    data_type,
                    station_id,
                    event_id,
                    dry_run,
                    known_event_ids,
                )
                if result is not None:
                    added_datasources.append(result)
                if duplicate_warning is not None:
                    duplicate_warnings.append(duplicate_warning)
                if on_progress is not None:
                    on_progress(done, total)

            if dry_run:
                logger.info("Dry run: displaying data that would be added.")
                if added_datasources:
                    session.flush()
                nested.rollback()
                logger.info("Dry run complete. Rolling back changes.")
                return (
                    added_datasources,
                    existing_station_ids,
                    existing_event_ids,
                    existing_seismogram_ids,
                    duplicate_warnings,
                )

        session.commit()
        logger.info("Data added successfully.")
        return (
            added_datasources,
            existing_station_ids,
            existing_event_ids,
            existing_seismogram_ids,
            duplicate_warnings,
        )

    except Exception as e:
        logger.error(f"Failed to add data. Rolling back changes. Error: {e}")
        raise


def _seismogram_path(
    seismogram: IccsSeismogram, station: Station, data_dir: Path
) -> Path:
    """Compute the deterministic miniSEED path for a seismogram.

    The filename is derived from the station identity and the seismogram's
    begin time, so re-ingesting the same triple again resolves to the same
    `sourcename` and is deduped by `_link_seismogram`/`_link_datasource`
    rather than creating a duplicate.
    """

    filename = (
        f"{station.network}.{station.name}.{station.location}.{station.channel}"
        f"__{seismogram.begin_time:%Y%m%dT%H%M%S%f}.mseed"
    )
    return data_dir / filename


def _persist(seismogram: IccsSeismogram, station: Station, path: Path) -> None:
    """Write a seismogram's waveform to `path` as miniSEED."""

    write_mseed(
        [
            (
                MiniStationCode(
                    network=station.network,
                    name=station.name,
                    location=station.location,
                    channel=station.channel,
                ),
                seismogram,
            )
        ],
        path,
    )


def add_seismograms_to_project(
    session: Session,
    items: Sequence[tuple[IccsSeismogram, Station, Event]],
    *,
    data_dir: str | os.PathLike[str],
    dry_run: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[list[AimbatDataSource], set[UUID], set[UUID], set[UUID], list[str]]:
    """Ingest already-built (seismogram, station, event) triples directly.

    The general-purpose counterpart to `add_data_to_project` for a caller
    that already has pysmo `Seismogram`/`Station`/`Event`-shaped objects in
    memory - fetched from a web service, built in a notebook, or produced by
    a library such as `pysmo.tools.project.PysmoProject` - with no file
    round-trip through a `DataType` AIMBAT already understands. Each
    seismogram's waveform is persisted as a miniSEED file under `data_dir`
    so it can be read back later like any other data source; station and
    event metadata are taken directly from the objects given.

    Every triple must carry a real `Event`: `AimbatSeismogram.event_id` is a
    required foreign key, and AIMBAT's processing model (ICCS, MCCC,
    snapshots, the active-event mechanism) is per-event throughout, so an
    event-less seismogram would have nothing to attach to. Reuse the same
    `Event` object across several triples to link them to one event -
    `_link_event`'s near-duplicate detection still applies, so a second,
    slightly different `Event` object (e.g. from a re-run) resolves to the
    same row rather than duplicating it.

    Args:
        session: The SQLModel database session.
        items: Sequence of `(seismogram, station, event)` triples to add.
        data_dir: Directory the persisted miniSEED files are written to.
            Created (with any missing parents) if it does not exist yet.
        dry_run: If True, do not commit changes to the database.
        on_progress: Optional callback invoked as `on_progress(done, total)`
            after each triple is processed, for callers that want to
            display progress.

    Returns:
        Same 5-tuple shape as `add_data_to_project`:
        `(added_datasources, existing_station_ids, existing_event_ids,
        existing_seismogram_ids, duplicate_warnings)`.

    Raises:
        ValueError: If a near-duplicate event falls in the "ambiguous gap"
            band (see `add_data_to_project`).
    """

    logger.info(f"Adding {len(items)} seismogram(s) to project directly.")

    data_dir = Path(data_dir)

    existing_station_ids = set(session.exec(select(AimbatStation.id)).all())
    existing_event_ids = set(session.exec(select(AimbatEvent.id)).all())
    existing_seismogram_ids = set(session.exec(select(AimbatSeismogram.id)).all())

    known_event_ids = set(existing_event_ids)

    try:
        added_datasources: list[AimbatDataSource] = []
        duplicate_warnings: list[str] = []
        pending_writes: list[tuple[IccsSeismogram, Station, Path]] = []
        total = len(items)
        with session.begin_nested() as nested:
            for done, (seismogram, station, event) in enumerate(items, start=1):
                aimbat_station = _link_station(
                    session, AimbatStation.model_validate(station)
                )

                new_aimbat_event = AimbatEvent.model_validate(
                    event, update={"parameters": AimbatEventParameters()}
                )
                label = f"{station.network}.{station.name}"
                aimbat_event, duplicate_warning = _link_event(
                    session, new_aimbat_event, dry_run, known_event_ids, label
                )
                if duplicate_warning is not None:
                    duplicate_warnings.append(duplicate_warning)

                path = _seismogram_path(seismogram, station, data_dir)
                sourcename, datatype = str(path), DataType.MSEED
                already_persisted = (
                    session.exec(
                        select(AimbatDataSource.id).where(
                            AimbatDataSource.sourcename == sourcename
                        )
                    ).first()
                    is not None
                )
                if already_persisted:
                    message = _format_seismogram_collision_message(label, sourcename)
                    logger.warning(message)
                    if dry_run:
                        duplicate_warnings.append(message)
                else:
                    # Writing is deferred until the whole batch has been
                    # validated and linked, so a later triple's failure (e.g.
                    # an ambiguous-gap event) never leaves earlier triples'
                    # files orphaned on disk with no committed DB row.
                    pending_writes.append((seismogram, station, path))

                new_aimbat_seismogram = AimbatSeismogram.model_validate(
                    seismogram,
                    update={
                        "t0": seismogram.t0,
                        "parameters": AimbatSeismogramParameters(),
                    },
                )
                aimbat_seismogram = _link_seismogram(
                    session, new_aimbat_seismogram, sourcename
                )
                aimbat_seismogram.station = aimbat_station
                aimbat_seismogram.event = aimbat_event

                logger.debug(
                    f"Linking seismogram from {sourcename} to "
                    f"Station={aimbat_station.name} and EventTime={aimbat_event.time}."
                )

                aimbat_data_source = _link_datasource(
                    session, sourcename, datatype, aimbat_seismogram
                )
                added_datasources.append(aimbat_data_source)

                if on_progress is not None:
                    on_progress(done, total)

            if dry_run:
                logger.info("Dry run: displaying data that would be added.")
                if added_datasources:
                    session.flush()
                nested.rollback()
                logger.info("Dry run complete. Rolling back changes.")
                return (
                    added_datasources,
                    existing_station_ids,
                    existing_event_ids,
                    existing_seismogram_ids,
                    duplicate_warnings,
                )

            if pending_writes:
                data_dir.mkdir(parents=True, exist_ok=True)
                written: list[Path] = []
                try:
                    for (
                        pending_seismogram,
                        pending_station,
                        pending_path,
                    ) in pending_writes:
                        _persist(pending_seismogram, pending_station, pending_path)
                        written.append(pending_path)
                except Exception:
                    for written_path in written:
                        written_path.unlink(missing_ok=True)
                    raise

        session.commit()
        logger.info("Data added successfully.")
        return (
            added_datasources,
            existing_station_ids,
            existing_event_ids,
            existing_seismogram_ids,
            duplicate_warnings,
        )

    except Exception as e:
        logger.error(f"Failed to add data. Rolling back changes. Error: {e}")
        raise


def get_data_for_event(session: Session, event_id: UUID) -> Sequence[AimbatDataSource]:
    """Return the data sources belonging to the given event.

    Args:
        session: Database session.
        event_id: UUID of the AimbatEvent.

    Returns:
        Sequence of AimbatDataSource objects belonging to the event.
    """

    logger.debug(f"Getting data sources for event {event_id}.")

    statement = (
        select(AimbatDataSource)
        .join(AimbatSeismogram)
        .where(AimbatSeismogram.event_id == event_id)
    )
    return session.exec(statement).all()


def dump_data_table(
    session: Session,
    event_id: UUID | None = None,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return AIMBAT datasources table as a JSON-serialisable list of dicts.

    Args:
        session: Database session.
        event_id: UUID of the event to filter data sources by. If None, all data sources are returned.
        by_alias: Whether to use field aliases.
        by_title: Whether to use field titles (from the Pydantic model) for the
            field names in the output. Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.

    Returns:
        Aimbat datasources table as a list of dicts.
    """
    logger.debug("Dumping AIMBAT datasources table to json.")

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    adapter: TypeAdapter[Sequence[AimbatDataSource]] = TypeAdapter(
        Sequence[AimbatDataSource]
    )

    if event_id is not None:
        data_source = get_data_for_event(session, event_id)
    else:
        data_source = session.exec(select(AimbatDataSource)).all()

    data = adapter.dump_python(
        data_source, exclude=exclude, by_alias=by_alias, mode="json"
    )

    if by_title:
        title_map = get_title_map(AimbatDataSource)
        return [{title_map.get(k, k): v for k, v in row.items()} for row in data]

    return data
