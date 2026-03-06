"""
AIMBAT command line interface entrypoint for all other commands.

This is the main command line interface for AIMBAT. It must be executed with a
command (as specified below) to actually do anything. Help for individual
commands is available by typing `aimbat COMMAND --help`.

## IDs

Every record in AIMBAT (event, seismogram, station, snapshot, …) has a UUID.
Tables display each UUID truncated to the shortest prefix that is unique within
that table. When a command asks for an ID you may supply any prefix long enough
to identify the record unambiguously — from the shortest displayed prefix up to
the full UUID. Dashes are optional.
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
app.command("aimbat._cli.align:app", name="align")
app.command("aimbat._cli.data:app", name="data")
app.command("aimbat._cli.event:app", name="event")
app.command("aimbat._cli.pick:app", name="pick")
app.command("aimbat._cli.plot:app", name="plot")
app.command("aimbat._cli.project:app", name="project")
app.command("aimbat._cli.station:app", name="station")
app.command("aimbat._cli.seismogram:app", name="seismogram")
app.command("aimbat._cli.snapshot:app", name="snapshot")
app.command("aimbat._cli.utils:app", name="utils")
app.command("aimbat._tui.app:main", name="tui")
app.command("aimbat._cli.shell:app", name="shell")


if __name__ == "__main__":
    try:
        app()
    except Exception:
        console.print_exception(show_locals=True)
        sys.exit(1)
