"""Module to add seismogram files to an AIMBAT project and view information about them."""

from datetime import timedelta
from aimbat.lib.defaults import defaults_get_value
from aimbat.lib.models import (
    AimbatFile,
    AimbatFileCreate,
    AimbatStation,
    AimbatEvent,
    AimbatEventParameter,
    AimbatSeismogram,
    AimbatSeismogramParameter,
)
from aimbat.lib.db import engine
from aimbat.lib.common import AIMBAT_FILE_TYPES, AimbatFileType
from aimbat.lib.io import read_metadata_from_file
from pathlib import Path
from sqlmodel import Session, select
import click
from rich.progress import track
from rich.console import Console
from rich.table import Table


def add_files(
    data_files: list[Path], filetype: AimbatFileType, disable_progress: bool = True
) -> None:
    """Add files to the AIMBAT database.

    Parameters:
        data_files: List of filepaths of the data files.
        filetype: Type of data file (e.g. sac).
        disable_progress_bar: Do not display progress bar.
    """
    with Session(engine) as session:
        for filename in track(
            sequence=data_files,
            description="Adding files ...",
            disable=disable_progress,
        ):
            aimbatfilecreate = AimbatFileCreate(
                filename=str(filename), filetype=filetype
            )
            aimbatfile = AimbatFile.model_validate(aimbatfilecreate)
            statement = select(AimbatFile).where(
                AimbatFile.filename == aimbatfile.filename
            )
            if session.exec(statement).first() is None:
                session.add(aimbatfile)

        session.commit()
    update_metadata(disable_progress)


def update_metadata(disable_progress: bool = True) -> None:
    """Update or add metadata by reading all files whose paths are stored
    in the AIMBAT project.

    Parameters:
        disable_progress_bar: Do not display progress bar.
    """

    with Session(engine) as session:
        for aimbatfile in track(
            sequence=session.exec(select(AimbatFile)).all(),
            description="Parsing data ...",
            disable=disable_progress,
        ):
            seismogram, station, event, t0 = read_metadata_from_file(
                aimbatfile.filename, aimbatfile.filetype
            )

            select_aimbatstation = select(AimbatStation).where(
                AimbatStation.name == station.name
                and AimbatStation.network == station.network
            )
            aimbatstation = session.exec(select_aimbatstation).first()
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
            aimbatevent = session.exec(select_aimbatevent).first()
            if aimbatevent is None:
                aimbatevent = AimbatEvent.model_validate(
                    event, update={"time_db": event.time}
                )
            else:
                aimbatevent.latitude = event.latitude
                aimbatevent.longitude = event.longitude
                aimbatevent.depth = event.depth

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
                window_width = defaults_get_value("initial_time_window_width")
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

        session.commit()


def print_table() -> None:
    """Prints a pretty table with AIMBAT data."""

    table = Table(title="AIMBAT Data")

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("filename", justify="center", style="cyan", no_wrap=True)
    table.add_column("filetype", justify="center", style="magenta")

    with Session(engine) as session:
        for file in session.exec(select(AimbatFile)).all():
            table.add_row(
                str(file.id),
                str(file.filename),
                str(file.filetype),
            )

    console = Console()
    console.print(table)


@click.group("data")
def cli() -> None:
    """Manage data in the AIMBAT project."""
    pass


@cli.command("add")
@click.option(
    "--filetype",
    type=click.Choice(AIMBAT_FILE_TYPES, case_sensitive=False),
    default="sac",
    help="File type.",
)
@click.argument("data_files", nargs=-1, type=click.Path(exists=True), required=True)
def cli_add(data_files: list[Path], filetype: AimbatFileType) -> None:
    """Add or update data files in the AIMBAT project."""
    add_files(data_files, filetype, disable_progress=False)


@cli.command("list")
def cli_list() -> None:
    """Print information on the data stored in AIMBAT."""
    print_table()


if __name__ == "__main__":
    cli()
