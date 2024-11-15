from aimbat.lib.db import engine
from aimbat.lib.models import AimbatStation
from aimbat.lib.common import cli_enable_debug
import click
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select
from icecream import ic  # type: ignore

ic.disable()


def print_table() -> None:
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


@click.group("station")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """View and manage stations in the AIMBAT project."""
    cli_enable_debug(ctx)


@cli.command("list")
def cli_list() -> None:
    """Print information on the stations stored in AIMBAT."""
    ic()
    print_table()


if __name__ == "__main__":
    cli(obj={})
