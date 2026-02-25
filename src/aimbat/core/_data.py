import os
from aimbat.core import get_active_event
from aimbat.logger import logger
from aimbat.aimbat_types import DataType
from aimbat.utils import (
    uuid_shortener,
    make_table,
    TABLE_STYLING,
    json_to_table,
)
from aimbat.io import create_seismogram, create_station, create_event
from aimbat.models import (
    AimbatDataSource,
    AimbatDataSourceCreate,
    AimbatStation,
    AimbatEvent,
    AimbatSeismogram,
)
from sqlmodel import Session, select
from pydantic import TypeAdapter
from collections.abc import Sequence
from rich.progress import track
from rich.console import Console

__all__ = [
    "add_data_to_project",
    "get_data_for_active_event",
    "print_data_table",
    "dump_data_table_to_json",
]


def _create_station(
    session: Session, datasource: str | os.PathLike, datatype: DataType
) -> AimbatStation:
    """Create a new AimbatStation if it doesn't exist yet, or use existing one."""

    new_aimbat_station = create_station(datasource, datatype)

    select_aimbat_station = (
        select(AimbatStation)
        .where(AimbatStation.name == new_aimbat_station.name)
        .where(AimbatStation.network == new_aimbat_station.network)
        .where(AimbatStation.channel == new_aimbat_station.channel)
        .where(AimbatStation.location == new_aimbat_station.location)
    )
    aimbat_station = session.exec(select_aimbat_station).one_or_none()

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
    session: Session, datasource: str | os.PathLike, datatype: DataType
) -> AimbatEvent:
    """Create a new AimbatEvent if it doesn't exist yet, or use existing one."""

    new_aimbat_event = create_event(datasource, datatype)

    select_aimbat_event = select(AimbatEvent).where(
        AimbatEvent.time == new_aimbat_event.time
    )
    aimbat_event = session.exec(select_aimbat_event).one_or_none()

    if aimbat_event is None:
        aimbat_event = new_aimbat_event
        logger.debug(f"Adding event {aimbat_event.time} to project.")
        session.add(aimbat_event)
    else:
        logger.debug(
            f"Using existing event {aimbat_event.time} instead of adding new one."
        )
    return aimbat_event


def _create_seismogram(
    session: Session, datasource: str | os.PathLike, datatype: DataType
) -> AimbatSeismogram:
    """Create a new AimbatSeismogram if it doesn't exist yet, or use existing one."""

    new_aimbat_seismogram = create_seismogram(datasource, datatype)

    select_aimbat_seismogram = (
        select(AimbatSeismogram)
        .join(AimbatDataSource)
        .where(AimbatDataSource.sourcename == str(datasource))
    )

    aimbat_seismogram = session.exec(select_aimbat_seismogram).one_or_none()
    if aimbat_seismogram is None:
        logger.debug(f"Adding seismogram with data source {datasource} to project.")
        aimbat_seismogram = new_aimbat_seismogram
        session.add(aimbat_seismogram)
    else:
        logger.debug(
            f"Using existing seismogram with data source {datasource} instead of adding new one."
        )
    return aimbat_seismogram


def _add_datasource(
    session: Session, datasource: str | os.PathLike, datatype: DataType
) -> AimbatDataSource:
    """Add a data source to the AIMBAT database, creating related station, event and seismogram if necessary."""
    aimbat_station = _create_station(session, datasource, datatype)
    aimbat_event = _create_event(session, datasource, datatype)
    aimbat_seismogram = _create_seismogram(session, datasource, datatype)

    # TODO: perhaps adding potentially updated station and event information should be optional?
    aimbat_seismogram.station = aimbat_station
    aimbat_seismogram.event = aimbat_event

    # Create AimbatDataSource instance with relationship to AimbatSeismogram
    select_aimbat_data_source = select(AimbatDataSource).where(
        AimbatDataSource.sourcename == str(datasource)
    )
    aimbat_data_source = session.exec(select_aimbat_data_source).one_or_none()
    if aimbat_data_source is None:
        logger.debug(f"Adding data source {datasource} to project.")
        aimbat_data_source_create = AimbatDataSourceCreate(
            sourcename=str(datasource), datatype=datatype
        )
        aimbat_data_source = AimbatDataSource.model_validate(
            aimbat_data_source_create,
            update={"seismogram": aimbat_seismogram},
        )

    else:
        logger.debug(
            f"Using existing data source {datasource} instead of adding new one."
        )
        aimbat_data_source.seismogram = aimbat_seismogram
    session.add(aimbat_data_source)
    return aimbat_data_source


def _print_dry_run_results(
    added_datasources: Sequence[AimbatDataSource],
    existing_station_ids: set,
    existing_event_ids: set,
    existing_seismogram_ids: set,
) -> None:
    """Print a summary table showing which entities were added vs skipped."""
    bool_fmt = TABLE_STYLING.bool_formatter
    json_to_table(
        [
            {
                "Filename": str(ds.sourcename),
                "Station": ds.seismogram.station_id not in existing_station_ids,
                "Event": ds.seismogram.event_id not in existing_event_ids,
                "Seismogram": ds.seismogram_id not in existing_seismogram_ids,
            }
            for ds in added_datasources
        ],
        title="Dry Run: Data to be added",
        formatters={
            "Station": bool_fmt,
            "Event": bool_fmt,
            "Seismogram": bool_fmt,
        },
    )
    new_stations = sum(
        ds.seismogram.station_id not in existing_station_ids for ds in added_datasources
    )
    new_events = sum(
        ds.seismogram.event_id not in existing_event_ids for ds in added_datasources
    )
    new_seismograms = sum(
        ds.seismogram_id not in existing_seismogram_ids for ds in added_datasources
    )
    console = Console()
    console.print(
        f"\n{new_stations} station(s) added, "
        f"{len(added_datasources) - new_stations} skipped. "
        f"{new_events} event(s) added, "
        f"{len(added_datasources) - new_events} skipped. "
        f"{new_seismograms} seismogram(s) added, "
        f"{len(added_datasources) - new_seismograms} skipped."
    )


def add_data_to_project(
    session: Session,
    data_sources: Sequence[str | os.PathLike],
    data_type: DataType,
    dry_run: bool = False,
    disable_progress_bar: bool = True,
) -> None:
    """Add files to the AIMBAT database.

    Args:
        session: The SQLModel database session.
        data_sources: List of data sources to add.
        data_type: Type of data.
        dry_run: If True, do not commit changes to the database.
        disable_progress_bar: Do not display progress bar.
    """

    logger.info(f"Adding {len(data_sources)} {data_type} files to project.")

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
                added_datasources.append(
                    _add_datasource(session, datasource, data_type)
                )

            if dry_run:
                logger.info("Dry run: displaying data that would be added.")
                session.flush()
                _print_dry_run_results(
                    added_datasources,
                    existing_station_ids,
                    existing_event_ids,
                    existing_seismogram_ids,
                )
                nested.rollback()
                logger.info("Dry run complete. Rolling back changes.")
                return

        session.commit()
        logger.info("Data added successfully.")

    except Exception as e:
        logger.error(f"Failed to add data. Rolling back changes. Error: {e}")
        raise


def get_data_for_active_event(session: Session) -> Sequence[AimbatDataSource]:
    """Returns the data sources belonging to the active event.

    Args:
        session: Database session.

    Returns:
        Sequence of AimbatDataSource objects belonging to the active event.
    """

    logger.info("Getting data sources for active event.")

    statement = (
        select(AimbatDataSource)
        .join(AimbatSeismogram)
        .join(AimbatEvent)
        .where(AimbatEvent.active == 1)
    )
    return session.exec(statement).all()


def print_data_table(session: Session, short: bool, all_events: bool = False) -> None:
    """Print a pretty table with information about the data sources in the database.

    Args:
        short: Shorten UUIDs and format data.
        all_events: Print all files instead of limiting to the active event.
    """

    logger.info("Printing data sources table.")

    if all_events:
        aimbat_data_sources = session.exec(select(AimbatDataSource)).all()
        title = "Data sources for all events"
    else:
        active_event = get_active_event(session)
        aimbat_data_sources = get_data_for_active_event(session)
        time = (
            active_event.time.strftime("%Y-%m-%d %H:%M:%S")
            if short
            else active_event.time
        )
        id = uuid_shortener(session, active_event) if short else active_event.id
        title = f"Data sources for event {time} (ID={id})"

    logger.debug(f"Found {len(aimbat_data_sources)} files in total.")

    rows = [
        [
            uuid_shortener(session, a) if short else str(a.id),
            str(a.datatype),
            str(a.sourcename),
            (uuid_shortener(session, a.seismogram) if short else str(a.seismogram.id)),
        ]
        for a in aimbat_data_sources
    ]

    table = make_table(title=title)

    table.add_column(
        "ID (shortened)" if short else "ID",
        justify="center",
        style=TABLE_STYLING.id,
        no_wrap=True,
    )
    table.add_column("Datatype", justify="center", style=TABLE_STYLING.mine)
    table.add_column("Filename", justify="left", style=TABLE_STYLING.mine, no_wrap=True)
    table.add_column(
        "Seismogram ID", justify="center", style=TABLE_STYLING.linked, no_wrap=True
    )

    for row in rows:
        table.add_row(*row)

    console = Console()
    console.print(table)


def dump_data_table_to_json(session: Session) -> str:
    """Dump the table data to json."""

    logger.info("Dumping AIMBAT datasources table to json.")

    adapter: TypeAdapter[Sequence[AimbatDataSource]] = TypeAdapter(
        Sequence[AimbatDataSource]
    )
    aimbat_datasource = session.exec(select(AimbatDataSource)).all()
    return adapter.dump_json(aimbat_datasource).decode("utf-8")
