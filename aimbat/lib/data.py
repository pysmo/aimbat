"""Manage seismogram files in a project."""

from aimbat.lib.common import logger, reverse_uuid_shortener
from aimbat.lib.event import get_active_event, uuid_dict_reversed
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
from pathlib import Path
from sqlmodel import Session, select
from collections.abc import Sequence
from rich.progress import track
from rich.console import Console
import aimbat.lib.defaults as defaults
import uuid


def file_uuid_dict_reversed(
    session: Session, min_length: int = 2
) -> dict[uuid.UUID, str]:
    return reverse_uuid_shortener(session.exec(select(AimbatFile.id)).all(), min_length)


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
        seismogram, station, event, t0 = read_metadata_from_file(
            session, filename, filetype
        )

        # Create AimbatStation instance
        select_aimbat_station = (
            select(AimbatStation)
            .where(AimbatStation.name == station.name)
            .where(AimbatStation.network == station.network)
        )
        aimbat_station = session.exec(select_aimbat_station).one_or_none()
        if aimbat_station is None:
            logger.debug(
                f"Adding station {station.name} - {station.network} to project."
            )
            aimbat_station = AimbatStation.model_validate(station)
            session.add(aimbat_station)
        else:
            logger.debug(
                f"Using existing station {aimbat_station.name} - {aimbat_station.network} instead of adding new one."
            )

        # Create AimbatEvent instance
        select_aimbat_event = select(AimbatEvent).where(AimbatEvent.time == event.time)
        aimbat_event = session.exec(select_aimbat_event).one_or_none()
        if aimbat_event is None:
            logger.debug(f"Adding event {event.time} to project.")
            event_parameter = AimbatEventParameters(
                window_pre=defaults.get_default(
                    session, ProjectDefault.INITIAL_WINDOW_PRE
                ),
                window_post=defaults.get_default(
                    session, ProjectDefault.INITIAL_WINDOW_POST
                ),
            )
            aimbat_event = AimbatEvent.model_validate(
                event, update={"parameters": event_parameter}
            )
            session.add(aimbat_event)
        else:
            logger.debug(
                f"Using existing event {aimbat_event.time} instead of adding new one."
            )

        # Create AimbatSeismogram instance with relationships to AimbatStation and AimbatEvent
        select_aimbat_seismogram = (
            select(AimbatSeismogram)
            .join(AimbatFile)
            .where(AimbatFile.filename == str(filename))
        )

        aimbat_seismogram = session.exec(select_aimbat_seismogram).one_or_none()
        if aimbat_seismogram is None:
            logger.debug(f"Adding seismogram with data source {filename} to project.")
            aimbat_seismogram = AimbatSeismogram(
                begin_time=seismogram.begin_time,
                delta=seismogram.delta,
                t0=t0,
                station=aimbat_station,
                event=aimbat_event,
                parameters=AimbatSeismogramParameters(),
            )
            session.add(aimbat_seismogram)
        else:
            logger.debug(
                f"Using existing seismogram with data source {filename} instead of adding new one."
            )

        # Create AimbatFile instance with relationship to AimbatSeismogram
        select_aimbat_file = select(AimbatFile).where(
            AimbatFile.filename == str(filename)
        )
        aimbat_file = session.exec(select_aimbat_file).one_or_none()
        if aimbat_file is None:
            logger.debug(f"Adding data source {filename} to project.")
            aimbat_file_create = AimbatFileCreate(
                filename=str(filename), filetype=filetype
            )
            aimbat_file = AimbatFile.model_validate(
                aimbat_file_create, update={"seismogram": aimbat_seismogram}
            )

        else:
            logger.debug(
                f"Using existing data source {filename} instead of adding new one."
            )
            aimbat_file.seismogram = aimbat_seismogram
        session.add(aimbat_file)

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


def print_data_table(session: Session, format: bool, all_events: bool = False) -> None:
    """Print a pretty table with AIMBAT data.

    Parameters:
        session: Database session.
        format: Print the output in a more human-readable format.
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
        if format:
            title = f"AIMBAT data for event {active_event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_dict_reversed(session)[active_event.id]})"
        else:
            title = f"AIMBAT data for event {active_event.time} (ID={active_event.id})"

    logger.debug(f"Found {len(aimbat_files)} files in total.")

    table = make_table(title=title)

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Filetype", justify="center", style="magenta")
    table.add_column("Filename", justify="left", style="cyan", no_wrap=True)

    for file in aimbat_files:
        table.add_row(
            file_uuid_dict_reversed(session)[file.id] if format else str(file.id),
            str(file.filetype),
            str(file.filename),
        )

    console = Console()
    console.print(table)
