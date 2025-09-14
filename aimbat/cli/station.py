"""View and manage stations."""

from aimbat.cli.common import CommonParameters
from typing import Annotated
from cyclopts import App, Parameter


def _print_station_table(db_url: str | None, all_events: bool) -> None:
    from aimbat.lib.station import print_station_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_station_table(session, all_events)


app = App(name="station", help=__doc__, help_format="markdown")


@app.command(name="list")
def cli_station_list(
    *,
    all_events: Annotated[bool, Parameter(name="all")] = False,
    common: CommonParameters | None = None,
) -> None:
    """Print information on the stations used in the active event.

    Parameters:
        all_events: Select stations for all events.
    """

    common = common or CommonParameters()

    _print_station_table(common.db_url, all_events)


if __name__ == "__main__":
    app()
