"""
AIMBAT command line interface entrypoint for all other commands.

This is the main command line interface for AIMBAT. It must be executed with a
command (as specified below) to actually do anything. Help for individual
commands is available by typing `aimbat COMMAND --help`.
"""

from importlib import metadata
from cyclopts import App
from rich.console import Console
import sys

try:
    __version__ = str(metadata.version("aimbat"))
except Exception:
    __version__ = "unknown"

console = Console()

app = App(version=__version__, help=__doc__, help_format="markdown", console=console)
app.command("aimbat.cli._align:app", name="align")
app.command("aimbat.cli._data:app", name="data")
app.command("aimbat.cli._event:app", name="event")
app.command("aimbat.cli._pick:app", name="pick")
app.command("aimbat.cli._plot:app", name="plot")
app.command("aimbat.cli._project:app", name="project")
app.command("aimbat.cli._station:app", name="station")
app.command("aimbat.cli._seismogram:app", name="seismogram")
app.command("aimbat.cli._snapshot:app", name="snapshot")
app.command("aimbat.cli._utils:app", name="utils")


if __name__ == "__main__":
    try:
        app()
    except Exception:
        console.print_exception(show_locals=True)
        sys.exit(1)
