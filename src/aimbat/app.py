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

import sys
from importlib import metadata

from cyclopts import App
from rich.console import Console

import aimbat._cli as cli

try:
    __version__ = str(metadata.version("aimbat"))
except Exception:
    __version__ = "unknown"

console = Console()

app = App(version=__version__, help=__doc__, help_format="markdown", console=console)
app.command(cli.align)
app.command(cli.data)
app.command(cli.event)
app.command(cli.tool)
app.command(cli.plot)
app.command(cli.project)
app.command(cli.seismogram)
app.command(cli.snapshot)
app.command(cli.station)
app.command(cli.utils)
app.command(cli.shell)
app.command(cli.tui)


if __name__ == "__main__":
    try:
        app()
    except Exception:
        console.print_exception(show_locals=True)
        sys.exit(1)
