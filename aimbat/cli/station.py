"""View and manage stations."""

from aimbat.lib.common import debug_callback
from typing import Annotated
import typer


def _print_station_table(db_url: str | None, all_events: bool) -> None:
    from aimbat.lib.station import print_station_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_station_table(session, all_events)


app = typer.Typer(
    name="station",
    no_args_is_help=True,
    callback=debug_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)


@app.command("list")
def station_cli_list(
    ctx: typer.Context,
    all_events: Annotated[
        bool, typer.Option("--all", help="Select stations for all events.")
    ] = False,
) -> None:
    """Print information on the stations used in the active event."""
    db_url = ctx.obj["DB_URL"]
    _print_station_table(db_url, all_events)


if __name__ == "__main__":
    app()
