import os
from collections.abc import Sequence
from typing import Any, Literal, overload
from uuid import UUID

from pydantic import TypeAdapter
from rich.progress import track
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

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
    AimbatSeismogram,
    AimbatStation,
    _AimbatDataSourceCreate,
)
from aimbat.utils import get_title_map

__all__ = [
    "add_data_to_project",
    "get_data_for_event",
    "dump_data_table",
]


def _create_station(
    session: Session, datasource: os.PathLike | str, datatype: DataType
) -> AimbatStation:
    """Create a new AimbatStation if it doesn't exist yet, or use existing one."""

    new_aimbat_station = create_station(datasource, datatype)

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


def _create_event(
    session: Session, datasource: os.PathLike | str, datatype: DataType
) -> AimbatEvent:
    """Create a new AimbatEvent if it doesn't exist yet, or use existing one."""

    new_aimbat_event = create_event(datasource, datatype)

    statement = select(AimbatEvent).where(AimbatEvent.time == new_aimbat_event.time)
    aimbat_event = session.exec(statement).one_or_none()

    if aimbat_event is None:
        aimbat_event = new_aimbat_event
        logger.debug(f"Adding event {aimbat_event.time} to project.")
        session.add(aimbat_event)
    else:
        logger.debug(
            f"Using existing event {aimbat_event.time} instead of adding new one."
        )
        if (
            new_aimbat_event.latitude != aimbat_event.latitude
            or new_aimbat_event.longitude != aimbat_event.longitude
            or new_aimbat_event.depth != aimbat_event.depth
        ):
            logger.warning(
                f"Event at {aimbat_event.time} matched by time but has different "
                f"location metadata in {datasource}. The existing record will be used."
            )
    return aimbat_event


def _create_seismogram(
    session: Session, datasource: os.PathLike | str, datatype: DataType
) -> AimbatSeismogram:
    """Create a new AimbatSeismogram if it doesn't exist yet, or use existing one."""

    new_aimbat_seismogram = create_seismogram(datasource, datatype)

    statement = (
        select(AimbatSeismogram)
        .join(AimbatDataSource)
        .where(AimbatDataSource.sourcename == str(datasource))
    )

    aimbat_seismogram = session.exec(statement).one_or_none()
    if aimbat_seismogram is None:
        logger.debug(f"Adding seismogram with data source {datasource} to project.")
        aimbat_seismogram = new_aimbat_seismogram
        session.add(aimbat_seismogram)
    else:
        logger.debug(
            f"Using existing seismogram with data source {datasource} instead of adding new one."
        )
    return aimbat_seismogram


def _process_datasource(
    session: Session,
    datasource: os.PathLike | str,
    datatype: DataType,
    station_id: UUID | None,
    event_id: UUID | None,
) -> AimbatDataSource | None:
    """Process a single data source, creating whichever entities the data type supports.

    Returns an `AimbatDataSource` when seismogram data is created, or `None`
    for station-only or event-only imports.
    """

    # Resolve station — use the provided UUID, extract from the source, or skip
    if station_id is not None:
        aimbat_station: AimbatStation | None = session.get(AimbatStation, station_id)
        logger.debug(
            f"Using station {getattr(aimbat_station, 'name', 'Unknown')} - {getattr(aimbat_station, 'network', 'Unknown')} (ID={station_id})."
        )
    elif supports_station_creation(datatype):
        aimbat_station = _create_station(session, datasource, datatype)
    else:
        aimbat_station = None

    # Resolve event — use the provided UUID, extract from the source, or skip
    if event_id is not None:
        aimbat_event: AimbatEvent | None = session.get(AimbatEvent, event_id)
        if aimbat_event is None:
            raise ValueError(f"No event found with ID={event_id}.")
        logger.debug(f"Using event {aimbat_event.time} (ID={event_id}).")
    elif supports_event_creation(datatype):
        aimbat_event = _create_event(session, datasource, datatype)
    else:
        aimbat_event = None

    # No seismogram creation → station/event-only import, nothing more to do
    if not supports_seismogram_creation(datatype):
        return None

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

    statement = select(AimbatDataSource).where(
        AimbatDataSource.sourcename == str(datasource)
    )
    aimbat_data_source = session.exec(statement).one_or_none()
    if aimbat_data_source is None:
        logger.debug(f"Adding data source {datasource} to project.")
        aimbat_data_source = AimbatDataSource.model_validate(
            _AimbatDataSourceCreate(sourcename=str(datasource), datatype=datatype),
            update={"seismogram": aimbat_seismogram},
        )
    else:
        logger.debug(
            f"Using existing data source {datasource} instead of adding new one."
        )
        aimbat_data_source.seismogram = aimbat_seismogram
    session.add(aimbat_data_source)
    return aimbat_data_source


@overload
def add_data_to_project(
    session: Session,
    data_sources: Sequence[os.PathLike | str],
    data_type: DataType,
    station_id: UUID | None = ...,
    event_id: UUID | None = ...,
    dry_run: Literal[False] = ...,
    disable_progress_bar: bool = ...,
) -> None: ...


@overload
def add_data_to_project(
    session: Session,
    data_sources: Sequence[os.PathLike | str],
    data_type: DataType,
    station_id: UUID | None = ...,
    event_id: UUID | None = ...,
    *,
    dry_run: Literal[True],
    disable_progress_bar: bool = ...,
) -> tuple[list[AimbatDataSource], set[UUID], set[UUID], set[UUID]]: ...


def add_data_to_project(
    session: Session,
    data_sources: Sequence[os.PathLike | str],
    data_type: DataType,
    station_id: UUID | None = None,
    event_id: UUID | None = None,
    dry_run: bool = False,
    disable_progress_bar: bool = True,
) -> tuple[list[AimbatDataSource], set[UUID], set[UUID], set[UUID]] | None:
    """Add data sources to the AIMBAT database.

    What gets created depends on which capabilities `data_type` supports:

    - Station + event + seismogram: all three records are created and linked,
      and an `AimbatDataSource` entry is stored.
    - Station or event only (e.g. `JSON_STATION`, `JSON_EVENT`): only the
      relevant metadata records are created; no seismogram or data source entry
      is stored.

    Use `station_id` or `event_id` to skip extracting station or event metadata
    from the data source and link to a pre-existing record instead.

    Args:
        session: The SQLModel database session.
        data_sources: List of data sources to add.
        data_type: Type of data.
        station_id: UUID of an existing station to use instead of extracting
            one from each data source.
        event_id: UUID of an existing event to use instead of extracting one
            from each data source.
        dry_run: If True, do not commit changes to the database.
        disable_progress_bar: Do not display progress bar.
    """

    logger.info(f"Adding {len(data_sources)} {data_type} data sources to project.")

    if station_id is not None and session.get(AimbatStation, station_id) is None:
        raise NoResultFound(f"No station found with ID {station_id}.")
    if event_id is not None and session.get(AimbatEvent, event_id) is None:
        raise NoResultFound(f"No event found with ID {event_id}.")

    # Snapshot existing IDs before entering the savepoint so we can identify
    # what would be new vs reused when running a dry run.
    if dry_run:
        existing_station_ids = set(session.exec(select(AimbatStation.id)).all())
        existing_event_ids = set(session.exec(select(AimbatEvent.id)).all())
        existing_seismogram_ids = set(session.exec(select(AimbatSeismogram.id)).all())

    try:
        added_datasources: list[AimbatDataSource] = []
        with session.begin_nested() as nested:
            for datasource in track(
                sequence=data_sources,
                description="Adding data ...",
                disable=disable_progress_bar,
            ):
                result = _process_datasource(
                    session, datasource, data_type, station_id, event_id
                )
                if result is not None:
                    added_datasources.append(result)

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
                )

        session.commit()
        logger.info("Data added successfully.")
        return None

    except Exception as e:
        logger.error(f"Failed to add data. Rolling back changes. Error: {e}")
        raise


def get_data_for_event(session: Session, event_id: UUID) -> Sequence[AimbatDataSource]:
    """Returns the data sources belonging to the given event.

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
