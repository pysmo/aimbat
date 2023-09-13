from aimbat.lib import (
    project,
    defaults,
    checkdata,
    sampledata
)
from importlib import metadata
import click

try:
    __version__ = metadata.version("aimbat")
except Exception:
    __version__ = "unknown"


@click.group('aimbat')
@click.version_option(version=__version__)
def cli() -> None:
    """Command line interface entrypoint for all other commands.

    This is the main command line interface for AIMBAT. It must be executed with a
    command (as specified below) to actually do anything. Help for individual
    commands is available by typing aimbat COMMAND --help.
    """
    pass


cli.add_command(project.cli)
cli.add_command(defaults.cli)
cli.add_command(sampledata.cli)
cli.add_command(checkdata.cli)


if __name__ == "__main__":
    cli()
