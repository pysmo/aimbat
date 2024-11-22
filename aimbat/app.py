from aimbat.cli import (
    checkdata,
    data,
    defaults,
    event,
    project,
    sampledata,
    seismogram,
    snapshot,
    station,
    utils,
)
from importlib import metadata
import click


try:
    __version__ = metadata.version("aimbat")
except Exception:
    __version__ = "unknown"


@click.group("aimbat")
@click.option("--debug", is_flag=True, help="Print extra debug information.")
@click.option(
    "--use-qt",
    is_flag=True,
    help="Use pyqtgraph instead of matplotlib for plot (where applicable).",
)
@click.pass_context
@click.version_option(version=__version__)
def cli(ctx: click.Context, debug: bool, use_qt: bool) -> None:
    """Command line interface entrypoint for all other commands.

    This is the main command line interface for AIMBAT. It must be executed with a
    command (as specified below) to actually do anything. Help for individual
    commands is available by typing aimbat COMMAND --help.
    """
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug
    ctx.obj["USE_QT"] = use_qt


# @cli.command("gui")
# def gui() -> None:
#     """Launch AIMBAT graphical user interface."""
#     aimbat_main_gui()


cli.add_command(checkdata.checkdata_cli)
cli.add_command(data.data_cli)
cli.add_command(defaults.defaults_cli)
cli.add_command(event.event_cli)
cli.add_command(project.project_cli)
cli.add_command(sampledata.sampledata_cli)
cli.add_command(seismogram.seismogram_cli)
cli.add_command(snapshot.snapshot_cli)
cli.add_command(station.station_cli)
cli.add_command(utils.utils_cli)


if __name__ == "__main__":
    cli(obj={})