from aimbat.lib.common import ic
from aimbat.lib.db import engine
from aimbat.lib.event import get_active_event
from aimbat.lib.models import AimbatStation
from aimbat.lib.misc.rich_utils import make_table
from rich.console import Console
from sqlmodel import Session, select


def print_station_table(session: Session, all_events: bool = False) -> None:
    """Prints a pretty table with AIMBAT stations."""
    ic()
    ic(engine)

    title = "AIMBAT stations for all events"
    aimbat_stations = None

    if all_events:
        aimbat_stations = session.exec(select(AimbatStation)).all()
    else:
        active_event = get_active_event(session)
        aimbat_stations = active_event.stations
        title = f"AIMBAT stations for event {active_event.time} (ID={active_event.id})"

    table = make_table(title=title)

    table.add_column("id", justify="right", style="cyan", no_wrap=True)
    table.add_column("Name & Network", justify="center", style="cyan", no_wrap=True)
    table.add_column("Latitude", justify="center", style="magenta")
    table.add_column("Longitude", justify="center", style="magenta")
    table.add_column("Elevation", justify="center", style="magenta")
    table.add_column("# Seismograms", justify="center", style="green")
    if all_events:
        table.add_column("# Events", justify="center", style="green")

    for aimbat_station in aimbat_stations:
        assert aimbat_station.id is not None
        events = {i.event_id for i in aimbat_station.seismograms}
        if all_events:
            table.add_row(
                str(aimbat_station.id),
                f"{aimbat_station.name} - {aimbat_station.network}",
                str(aimbat_station.latitude),
                str(aimbat_station.longitude),
                str(aimbat_station.elevation),
                str(len(aimbat_station.seismograms)),
                str(len(events)),
            )
        else:
            table.add_row(
                str(aimbat_station.id),
                f"{aimbat_station.name} - {aimbat_station.network}",
                str(aimbat_station.latitude),
                str(aimbat_station.longitude),
                str(aimbat_station.elevation),
                str(len(aimbat_station.seismograms)),
            )

    console = Console()
    console.print(table)
