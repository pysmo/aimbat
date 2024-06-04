from datetime import timedelta
from aimbat.lib.defaults import defaults_get_value
from aimbat.lib.models import (
    AimbatEventParameter,
    AimbatFile,
    AimbatFileCreate,
    AimbatParameterSet,
    AimbatSeismogramParameter,
    AimbatStation,
    AimbatEvent,
    AimbatSeismogram,
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
            results = session.exec(statement)
            if results.first() is None:
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

            select_aimbatevent = select(AimbatEvent).where(
                AimbatEvent.time == event.time
            )
            aimbatevent = session.exec(select_aimbatevent).first()
            if aimbatevent is None:
                aimbatevent = AimbatEvent.model_validate(event)
            else:
                aimbatevent.latitude = event.latitude
                aimbatevent.longitude = event.longitude
                aimbatevent.depth = event.depth

            session.add(aimbatstation)
            session.add(aimbatevent)
            session.commit()

            select_aimbatseismogram = select(AimbatSeismogram).where(
                AimbatSeismogram.file_id == aimbatfile.id
            )
            aimbatseismogram = session.exec(select_aimbatseismogram).first()
            if aimbatseismogram is None:
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
                seismogram_parameter = AimbatSeismogramParameter()
                parameter = AimbatParameterSet(
                    event_parameter=event_parameter,
                    seismogram_parameter=seismogram_parameter,
                )
                aimbatseismogram = AimbatSeismogram(
                    begin_time=seismogram.begin_time,
                    delta=seismogram.delta,
                    t0=t0,
                    file_id=aimbatfile.id,
                    station_id=aimbatstation.id,
                    event_id=aimbatevent.id,
                    parameter=parameter,
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


def stations_print_table() -> None:
    """Prints a pretty table with AIMBAT stations."""

    table = Table(title="AIMBAT Stations")

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Name & Network", justify="center", style="cyan", no_wrap=True)
    table.add_column("Latitude", justify="center", style="magenta")
    table.add_column("Longitude", justify="center", style="magenta")
    table.add_column("Elevation", justify="center", style="magenta")
    table.add_column("# Seismograms", justify="center", style="green")
    table.add_column("# Events", justify="center", style="green")

    with Session(engine) as session:
        all_stations = session.exec(select(AimbatStation)).all()
        if all_stations is not None:
            for station in all_stations:
                assert station.id is not None
                events = {i.event_id for i in station.seismograms}
                table.add_row(
                    str(station.id),
                    f"{station.name} - {station.network}",
                    str(station.latitude),
                    str(station.longitude),
                    str(station.elevation),
                    str(len(station.seismograms)),
                    str(len(events)),
                )

    console = Console()
    console.print(table)


def events_print_table() -> None:
    """Prints a pretty table with AIMBAT events."""

    table = Table(title="AIMBAT Events")

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Date & Time", justify="center", style="cyan", no_wrap=True)
    table.add_column("Latitude", justify="center", style="magenta")
    table.add_column("Longitude", justify="center", style="magenta")
    table.add_column("Depth", justify="center", style="magenta")
    table.add_column("# Seismograms", justify="center", style="green")
    table.add_column("# Stations", justify="center", style="green")

    with Session(engine) as session:
        all_events = session.exec(select(AimbatEvent)).all()
        if all_events is not None:
            for event in all_events:
                assert event.id is not None
                stations = {i.station_id for i in event.seismograms}
                table.add_row(
                    str(event.id),
                    str(event.time),
                    str(event.latitude),
                    str(event.longitude),
                    str(event.depth),
                    str(len(event.seismograms)),
                    str(len(stations)),
                )

    console = Console()
    console.print(table)


def seismograms_print_table() -> None:
    """Prints a pretty table with AIMBAT seismograms."""

    table = Table(title="AIMBAT Seismograms")

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Filename", justify="center", style="cyan", no_wrap=True)
    table.add_column("Station ID", justify="center", style="magenta")
    table.add_column("Event ID", justify="center", style="magenta")

    with Session(engine) as session:
        all_seismograms = session.exec(select(AimbatSeismogram)).all()
        if all_seismograms is not None:
            for seismogram in all_seismograms:
                assert seismogram.id is not None
                table.add_row(
                    str(seismogram.id),
                    str(seismogram.file.filename),
                    str(seismogram.station.id),
                    str(seismogram.event.id),
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


@cli.group("list")
def cli_list() -> None:
    """List data from the AIMBAT project."""
    pass


@cli_list.command("stations")
def cli_list_stations() -> None:
    """Print information on the stations stored in AIMBAT."""
    stations_print_table()


@cli_list.command("events")
def cli_list_events() -> None:
    """Print information on the events stored in AIMBAT."""
    events_print_table()


@cli_list.command("seismograms")
def cli_list_seismograms() -> None:
    """Print information on the seismograms stored in AIMBAT."""
    seismograms_print_table()


if __name__ == "__main__":
    cli()
