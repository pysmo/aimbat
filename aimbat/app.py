"""
AIMBAT command line interface entrypoint for all other commands.

This is the main command line interface for AIMBAT. It must be executed with a
command (as specified below) to actually do anything. Help for individual
commands is available by typing `aimbat COMMAND --help`.
"""

from importlib import metadata
from cyclopts import App
from aimbat.cli import (
    data,
    defaults,
    event,
    processing,
    project,
    plot,
    seismogram,
    snapshot,
    station,
    utils,
)
from rich.console import Console
import sys

try:
    __version__ = str(metadata.version("aimbat"))
except Exception:
    __version__ = "unknown"

console = Console()

app = App(version=__version__, help=__doc__, help_format="markdown", console=console)
app.command(data.app)
app.command(defaults.app)
app.command(event.app)
app.command(processing.app)
app.command(project.app)
app.command(plot.app)
app.command(seismogram.app)
app.command(snapshot.app)
app.command(station.app)
app.command(utils.app)

if __name__ == "__main__":
    try:
        app()
    except Exception:
        console.print_exception()
        sys.exit(1)
