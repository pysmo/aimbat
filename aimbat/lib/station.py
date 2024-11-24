from aimbat.lib.common import ic
from aimbat.lib.db import engine
from aimbat.lib.models import AimbatStation
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select


def print_station_table(session: Session) -> None:
    """Prints a pretty table with AIMBAT stations."""
    ic()
    ic(engine)

    table = Table(title="AIMBAT Stations")

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Name & Network", justify="center", style="cyan", no_wrap=True)
    table.add_column("Latitude", justify="center", style="magenta")
    table.add_column("Longitude", justify="center", style="magenta")
    table.add_column("Elevation", justify="center", style="magenta")
    table.add_column("# Seismograms", justify="center", style="green")
    table.add_column("# Events", justify="center", style="green")

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
