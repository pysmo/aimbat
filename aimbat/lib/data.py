"""Manage seismogram files in a project."""

from aimbat.lib.common import logger
from aimbat.lib.defaults import get_default
from aimbat.lib.event import get_active_event
from aimbat.lib.io import read_metadata_from_file
from aimbat.lib.misc.rich_utils import make_table
from aimbat.lib.models import (
    AimbatFile,
    AimbatFileCreate,
    AimbatStation,
    AimbatEvent,
    AimbatEventParameters,
    AimbatSeismogram,
    AimbatSeismogramParameters,
)
from aimbat.lib.typing import ProjectDefault, SeismogramFileType
from datetime import timedelta
from pathlib import Path
from sqlmodel import Session, select
from collections.abc import Sequence
from rich.progress import track
from rich.console import Console


def add_files_to_project(
    session: Session,
    seismogram_files: list[Path],
    filetype: SeismogramFileType,
    disable_progress_bar: bool = True,
) -> None:
    """Add files to the AIMBAT database.

    Parameters:
        session: Database session.
        seismogram_files: List of filepaths of the data files.
        filetype: Type of data file.
        disable_progress_bar: Do not display progress bar.
    """

    logger.info(f"Adding {len(seismogram_files)} {filetype} files to project.")

    for filename in track(
        sequence=seismogram_files,
        description="Adding files ...",
        disable=disable_progress_bar,
    ):
        aimbatfilecreate = AimbatFileCreate(filename=str(filename), filetype=filetype)
        aimbatfile = AimbatFile.model_validate(aimbatfilecreate)
        statement = select(AimbatFile).where(AimbatFile.filename == aimbatfile.filename)
        if session.exec(statement).first() is None:
            logger.debug(f"Adding file {aimbatfile.filename} to database.")
            session.add(aimbatfile)
        else:
            logger.debug(f"File {aimbatfile.filename} already in database. Skipping.")

    session.commit()

    _update_metadata(session, disable_progress_bar)


def _update_metadata(session: Session, disable_progress_bar: bool = True) -> None:
    """Update or add metadata by reading all files whose paths are stored
    in the AIMBAT project.

    Parameters:
        session: Database session.
        disable_progress_bar: Do not display progress bar.
    """

    logger.info("Updating metadata for all files in project.")

    for aimbatfile in track(
        sequence=session.exec(select(AimbatFile)).all(),
        description="Parsing data ...",
        disable=disable_progress_bar,
    ):
        logger.debug(f"Reading metadata from file {aimbatfile.filename}")
        seismogram, station, event, t0 = read_metadata_from_file(
            session, aimbatfile.filename, aimbatfile.filetype
        )

        logger.debug(
            f"Adding or updating station {station.name=}.{station.network=}..."
        )
        select_aimbatstation = (
            select(AimbatStation)
            .where(AimbatStation.name == station.name)
            .where(AimbatStation.network == station.network)
        )
        aimbatstation = session.exec(select_aimbatstation).one_or_none()
        if aimbatstation is None:
            logger.debug(
                f"Adding station {station.name=}.{station.network=} to database."
            )
            aimbatstation = AimbatStation.model_validate(station)
        else:
            logger.debug(
                f"Updating existing station {station.name=}.{station.network=}."
            )
            aimbatstation.latitude = station.latitude
            aimbatstation.longitude = station.longitude
            aimbatstation.elevation = station.elevation
        session.add(aimbatstation)

        logger.debug(f"Adding or updating event {event.time}...")
        select_aimbatevent = select(AimbatEvent).where(AimbatEvent.time == event.time)
        aimbatevent = session.exec(select_aimbatevent).one_or_none()
        if aimbatevent is None:
            logger.debug(f"Adding event {event.time} to database.")
            aimbatevent = AimbatEvent.model_validate(event, update={"time": event.time})
        else:
            logger.debug(f"Updating existing event {event.time}.")
            aimbatevent.latitude = event.latitude
            aimbatevent.longitude = event.longitude
            aimbatevent.depth = event.depth

        if aimbatstation not in aimbatevent.stations:
            logger.debug(
                f"Registering station {aimbatstation} with event {aimbatevent}."
            )
            aimbatevent.stations.append(aimbatstation)

        session.add(aimbatevent)
        session.commit()

        logger.debug(f"Adding or updating seismogram for {aimbatfile.id=}...")
        select_aimbatseismogram = select(AimbatSeismogram).where(
            AimbatSeismogram.file_id == aimbatfile.id
        )
        aimbatseismogram = session.exec(select_aimbatseismogram).first()
        if aimbatseismogram is None:
            logger.debug(f"Adding seismogram for {aimbatfile.id=} to database.")
            aimbatseismogram = AimbatSeismogram(
                begin_time=seismogram.begin_time,
                delta=seismogram.delta,
                t0=t0,
                file_id=aimbatfile.id,
                station_id=aimbatstation.id,
                event_id=aimbatevent.id,
            )
        else:
            logger.debug(f"Updating existing seismogram for {aimbatfile.id=}.")
            aimbatseismogram.begin_time = seismogram.begin_time
            aimbatseismogram.delta = seismogram.delta
            aimbatseismogram.t0 = t0
            aimbatseismogram.cached_length = None
            aimbatseismogram.station_id = aimbatstation.id
            aimbatseismogram.event_id = aimbatevent.id

        session.add(aimbatseismogram)
        session.commit()

        logger.debug("Setting default paramaeters for new events and seismograms.")
        select_event_parameter = select(AimbatEventParameters).where(
            AimbatEventParameters.event_id == aimbatevent.id
        )
        event_parameter = session.exec(select_event_parameter).first()
        if event_parameter is None:
            logger.debug(
                f"Adding default parameters for event with id={aimbatevent.id}."
            )
            window_width = get_default(
                session, ProjectDefault.INITIAL_TIME_WINDOW_WIDTH
            )
            assert isinstance(window_width, timedelta)
            event_parameter = AimbatEventParameters(
                event_id=aimbatevent.id,
                window_pre=window_width / -2,
                window_post=window_width / 2,
            )
            session.add(event_parameter)

        select_seismogram_parameter = select(AimbatSeismogramParameters).where(
            AimbatSeismogramParameters.seismogram_id == aimbatseismogram.id
        )
        seismogram_parameter = session.exec(select_seismogram_parameter).first()
        if seismogram_parameter is None:
            logger.debug(
                f"Adding default parameters for seismogram with id={aimbatseismogram.id}."
            )
            seismogram_parameter = AimbatSeismogramParameters(
                seismogram_id=aimbatseismogram.id
            )
            session.add(seismogram_parameter)

    session.commit()


def get_data_for_active_event(session: Session) -> Sequence[AimbatFile]:
    """Returns the AimbatFiles belonging to the active event.

    Parameters:
        session: Database session.

    Returns:
        List of AimbatFiles.
    """

    logger.info("Getting aimbatfiles in active event.")

    select_files = (
        select(AimbatFile)
        .join(AimbatSeismogram)
        .join(AimbatEvent)
        .where(AimbatEvent.active == 1)
    )
    return session.exec(select_files).all()


def print_data_table(session: Session, all_events: bool = False) -> None:
    """Print a pretty table with AIMBAT data.

    Parameters:
        session: Database session.
        all_events: Print all files instead of limiting to the active event.
    """

    logger.info("Printing AIMBAT data table.")

    title = "AIMBAT data for all events"
    aimbat_files = None
    if all_events:
        aimbat_files = session.exec(select(AimbatFile)).all()
    else:
        active_event = get_active_event(session)
        aimbat_files = get_data_for_active_event(session)
        title = f"AIMBAT data for event {active_event.time} (ID={active_event.id})"

    logger.debug(f"Found {len(aimbat_files)} files in total.")

    table = make_table(title=title)

    table.add_column("id", justify="right", style="cyan", no_wrap=True)
    table.add_column("Filetype", justify="center", style="magenta")
    table.add_column("Filename", justify="left", style="cyan", no_wrap=True)

    for file in aimbat_files:
        table.add_row(str(file.id), str(file.filetype), str(file.filename))

    console = Console()
    console.print(table)
