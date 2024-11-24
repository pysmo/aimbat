"""View and manage stations."""

from aimbat.lib.common import debug_callback
import typer


def _print_station_table(db_url: str | None) -> None:
    from aimbat.lib.station import print_station_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_station_table(session)


app = typer.Typer(
    name="station",
    no_args_is_help=True,
    callback=debug_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)


@app.command("list")
def station_cli_list(ctx: typer.Context) -> None:
    """Print information on the stations stored in AIMBAT."""
    db_url = ctx.obj["DB_URL"]
    _print_station_table(db_url)


if __name__ == "__main__":
    app()
