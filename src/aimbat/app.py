"""
AIMBAT command line interface entrypoint for all other commands.

This is the main command line interface for AIMBAT. It must be executed with a
command (as specified below) to actually do anything. Help for individual
commands is available by typing `aimbat COMMAND --help`.
"""

from ._config import cli_settings_list
from .cli import (
    _align,
    _data,
    _event,
    _pick,
    _plot,
    _project,
    _station,
    _seismogram,
    _snapshot,
    _utils,
)
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
app.command(_align.app)
app.command(_data.app)
app.command(_event.app)
app.command(_pick.app)
app.command(_plot.app)
app.command(_project.app)
app.command(_station.app)
app.command(_seismogram.app)
app.command(cli_settings_list, name="settings")
app.command(_snapshot.app)
app.command(_utils.app)


if __name__ == "__main__":
    try:
        app()
    except Exception:
        console.print_exception(show_locals=True)
        sys.exit(1)
