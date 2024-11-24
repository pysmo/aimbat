"""Module to add seismogram files to an AIMBAT project and view information about them."""

from aimbat.lib.common import ic
from aimbat.lib.defaults import get_default
from aimbat.lib.types import AimbatFileType
from aimbat.lib.io import read_metadata_from_file
from aimbat.lib.models import (
    AimbatFile,
    AimbatFileCreate,
    AimbatStation,
    AimbatEvent,
    AimbatEventParameter,
    AimbatSeismogram,
    AimbatSeismogramParameter,
)
from datetime import timedelta
from pathlib import Path
from sqlmodel import Session, select
from rich.progress import track
from rich.console import Console
from rich.table import Table


def add_files_to_project(
    session: Session,
    seismogram_files: list[Path],
    filetype: AimbatFileType,
    disable_progress_bar: bool = True,
) -> None:
    """Add files to the AIMBAT database.

    Parameters:
        session: Database session.
        seismogram_files: List of filepaths of the data files.
        filetype: Type of data file (e.g. sac).
        disable_progress_bar: Do not display progress bar.
    """
    ic()
    ic(session)

    for filename in track(
        sequence=seismogram_files,
        description="Adding files ...",
        disable=disable_progress_bar,
    ):
        aimbatfilecreate = AimbatFileCreate(filename=str(filename), filetype=filetype)
        aimbatfile = AimbatFile.model_validate(aimbatfilecreate)
        statement = select(AimbatFile).where(AimbatFile.filename == aimbatfile.filename)
        if session.exec(statement).first() is None:
            session.add(aimbatfile)
        ic(aimbatfile)

    session.commit()

    _update_metadata(session, disable_progress_bar)


def _update_metadata(session: Session, disable_progress_bar: bool = True) -> None:
    """Update or add metadata by reading all files whose paths are stored
    in the AIMBAT project.

    Parameters:
        disable_progress_bar: Do not display progress bar.
    """
    ic()
    ic(session)

    for aimbatfile in track(
        sequence=session.exec(select(AimbatFile)).all(),
        description="Parsing data ...",
        disable=disable_progress_bar,
    ):
        seismogram, station, event, t0 = read_metadata_from_file(
            session, aimbatfile.filename, aimbatfile.filetype
        )

        select_aimbatstation = select(AimbatStation).where(
            AimbatStation.name == station.name
            and AimbatStation.network == station.network
        )
        aimbatstation = session.exec(select_aimbatstation).one_or_none()
        if aimbatstation is None:
            aimbatstation = AimbatStation.model_validate(station)
        else:
            aimbatstation.latitude = station.latitude
            aimbatstation.longitude = station.longitude
            aimbatstation.elevation = station.elevation
        session.add(aimbatstation)

        select_aimbatevent = select(AimbatEvent).where(
            AimbatEvent.time_db == event.time
        )
        aimbatevent = session.exec(select_aimbatevent).one_or_none()
        if aimbatevent is None:
            aimbatevent = AimbatEvent.model_validate(
                event, update={"time_db": event.time}
            )
        else:
            aimbatevent.latitude = event.latitude
            aimbatevent.longitude = event.longitude
            aimbatevent.depth = event.depth

        if aimbatstation not in aimbatevent.stations:
            aimbatevent.stations.append(aimbatstation)

        session.add(aimbatevent)
        session.commit()

        select_aimbatseismogram = select(AimbatSeismogram).where(
            AimbatSeismogram.file_id == aimbatfile.id
        )
        aimbatseismogram = session.exec(select_aimbatseismogram).first()
        if aimbatseismogram is None:
            aimbatseismogram = AimbatSeismogram(
                begin_time_db=seismogram.begin_time,
                delta=seismogram.delta,
                t0=t0,
                file_id=aimbatfile.id,
                station_id=aimbatstation.id,
                event_id=aimbatevent.id,
            )
        else:
            aimbatseismogram.begin_time = seismogram.begin_time
            aimbatseismogram.delta = seismogram.delta
            aimbatseismogram.t0 = t0
            aimbatseismogram.cached_length = None
            aimbatseismogram.station_id = aimbatstation.id
            aimbatseismogram.event_id = aimbatevent.id

        session.add(aimbatseismogram)
        session.commit()

        select_event_parameter = select(AimbatEventParameter).where(
            AimbatEventParameter.event_id == aimbatevent.id
        )
        event_parameter = session.exec(select_event_parameter).first()
        if event_parameter is None:
            window_width = get_default(session, "initial_time_window_width")
            assert isinstance(window_width, float)
            event_parameter = AimbatEventParameter(
                event_id=aimbatevent.id,
                window_pre=timedelta(seconds=window_width / -2),
                window_post=timedelta(seconds=window_width / 2),
            )
            session.add(event_parameter)

        select_seismogram_parameter = select(AimbatSeismogramParameter).where(
            AimbatSeismogramParameter.seismogram_id == aimbatseismogram.id
        )
        seismogram_parameter = session.exec(select_seismogram_parameter).first()
        if seismogram_parameter is None:
            seismogram_parameter = AimbatSeismogramParameter(
                seismogram_id=aimbatseismogram.id
            )
            session.add(seismogram_parameter)

        ic(aimbatfile.id, aimbatevent.id, aimbatstation.id)

    session.commit()


def print_data_table(session: Session) -> None:
    """Print a pretty table with AIMBAT data."""
    ic()

    table = Table(title="AIMBAT Data")

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("filename", justify="center", style="cyan", no_wrap=True)
    table.add_column("filetype", justify="center", style="magenta")

    for file in session.exec(select(AimbatFile)).all():
        table.add_row(
            str(file.id),
            str(file.filename),
            str(file.filetype),
        )

    console = Console()
    console.print(table)
