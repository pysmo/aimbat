"""
AIMBAT command line interface entrypoint for all other commands.

This is the main command line interface for AIMBAT. It must be executed with a
command (as specified below) to actually do anything. Help for individual
commands is available by typing aimbat COMMAND --help.
"""

from aimbat.lib.db import AIMBAT_DB_URL
from aimbat.cli import (
    data,
    defaults,
    event,
    project,
    seismogram,
    snapshot,
    station,
    utils,
)
from importlib import metadata
from rich import print
from rich.panel import Panel
from typing import Annotated
import typer

try:
    __version__ = str(metadata.version("aimbat"))
except Exception:
    __version__ = "unknown"


def app_callback(
    ctx: typer.Context,
    db_url: Annotated[
        str,
        typer.Option(help="Database connection URL."),
    ] = AIMBAT_DB_URL,
    debug: Annotated[bool, typer.Option(help="Run in debugging mode.")] = False,
    use_qt: Annotated[
        bool,
        typer.Option(
            help="Use pyqtgraph instead of matplotlib for plots (where applicable)."
        ),
    ] = False,
) -> None:
    """App callback function to add options and arguments to the main AIMBAT command."""
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug
    ctx.obj["DB_URL"] = db_url
    ctx.obj["USE_QT"] = use_qt


app = typer.Typer(
    name="aimbat",
    no_args_is_help=True,
    callback=app_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)
app.add_typer(project.app)
app.add_typer(data.app)
app.add_typer(defaults.app)
app.add_typer(event.app)
app.add_typer(station.app)
app.add_typer(seismogram.app)
app.add_typer(snapshot.app)
app.add_typer(utils.app)


@app.command("version")
def version() -> None:
    """Print the AIMBAT version."""
    print(
        Panel(
            __version__, title="AIMBAT version", title_align="left", border_style="dim"
        )
    )


if __name__ == "__main__":
    app()
