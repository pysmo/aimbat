from aimbat.logger import logger
from aimbat.lib.db import engine
from aimbat.lib.common import uuid_shortener, make_table, TABLE_STYLING
from aimbat.lib.event import get_active_event
from aimbat.lib.io import (
    create_seismogram,
    create_station,
    create_event,
    DataType,
)
from aimbat.lib.utils.json import dump_to_json
from aimbat.lib.models import (
    AimbatDataSource,
    AimbatDataSourceCreate,
    AimbatStation,
    AimbatEvent,
    AimbatSeismogram,
)
from sqlmodel import Session, select
from collections.abc import Sequence
from rich.progress import track
from rich.console import Console
import os


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


def add_files_to_project(
    datasources: Sequence[str | os.PathLike],
    datatype: DataType,
    disable_progress_bar: bool = True,
) -> None:
    """Add files to the AIMBAT database.

    Parameters:
        datasources: List of data sources to add.
        datatype: Type of data.
        disable_progress_bar: Do not display progress bar.
    """

    logger.info(f"Adding {len(datasources)} {datatype} files to project.")

    with Session(engine) as session:
        for datasource in track(
            sequence=datasources,
            description="Adding files ...",
            disable=disable_progress_bar,
        ):
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
                    aimbat_data_source_create, update={"seismogram": aimbat_seismogram}
                )

            else:
                logger.debug(
                    f"Using existing data source {datasource} instead of adding new one."
                )
                aimbat_data_source.seismogram = aimbat_seismogram
            session.add(aimbat_data_source)

        session.commit()


def get_data_for_active_event(session: Session) -> Sequence[AimbatDataSource]:
    """Returns the AimbatFiles belonging to the active event.

    Parameters:
        session: Database session.

    Returns:
        List of AimbatFiles.
    """

    logger.info("Getting aimbatfiles in active event.")

    select_files = (
        select(AimbatDataSource)
        .join(AimbatSeismogram)
        .join(AimbatEvent)
        .where(AimbatEvent.active == 1)
    )
    return session.exec(select_files).all()


def print_data_table(short: bool, all_events: bool = False) -> None:
    """Print a pretty table with AIMBAT data.

    Parameters:
        short: Shorten UUIDs and format data.
        all_events: Print all files instead of limiting to the active event.
    """

    logger.info("Printing AIMBAT data table.")

    with Session(engine) as session:
        if all_events:
            aimbat_data_sources = session.exec(select(AimbatDataSource)).all()
            title = "AIMBAT data for all events"
        else:
            active_event = get_active_event(session)
            aimbat_data_sources = get_data_for_active_event(session)
            time = (
                active_event.time.strftime("%Y-%m-%d %H:%M:%S")
                if short
                else active_event.time
            )
            id = uuid_shortener(session, active_event) if short else active_event.id
            title = f"AIMBAT data for event {time} (ID={id})"

        logger.debug(f"Found {len(aimbat_data_sources)} files in total.")

        rows = [
            [
                uuid_shortener(session, a) if short else str(a.id),
                str(a.datatype),
                str(a.sourcename),
                (
                    uuid_shortener(session, a.seismogram)
                    if short
                    else str(a.seismogram.id)
                ),
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
        table.add_column(
            "Filename", justify="left", style=TABLE_STYLING.mine, no_wrap=True
        )
        table.add_column(
            "Seismogram ID", justify="center", style=TABLE_STYLING.linked, no_wrap=True
        )

        for row in rows:
            table.add_row(*row)

        console = Console()
        console.print(table)


def dump_data_table() -> None:
    """Dump the table data to json."""

    logger.info("Dumping AIMBAT datasources table to json.")

    with Session(engine) as session:
        aimbat_data_sources = session.exec(select(AimbatDataSource)).all()
        dump_to_json(aimbat_data_sources)
