"""Module to add seismogram files to an AIMBAT project and view information about them."""

from aimbat.lib.common import cli_enable_debug, ic
from aimbat.lib.types import AIMBAT_FILE_TYPES, AimbatFileType
from pathlib import Path
import click


def cli_data_add_files(
    data_files: list[Path], filetype: AimbatFileType, disable_progress_bar: bool = True
) -> None:
    from aimbat.lib.data import data_add_files

    data_add_files(data_files, filetype, disable_progress_bar=disable_progress_bar)


def cli_data_print_table() -> None:
    from aimbat.lib.data import data_print_table

    data_print_table()


@click.group("data")
@click.pass_context
def data_cli(ctx: click.Context) -> None:
    """Manage data in the AIMBAT project."""
    cli_enable_debug(ctx)


@data_cli.command("add")
@click.option(
    "--filetype",
    type=click.Choice(AIMBAT_FILE_TYPES, case_sensitive=False),
    default="sac",
    help="File type.",
)
@click.argument("data_files", nargs=-1, type=click.Path(exists=True), required=True)
def cli_add(data_files: list[Path], filetype: AimbatFileType) -> None:
    """Add or update data files in the AIMBAT project."""
    cli_data_add_files(data_files, filetype, disable_progress_bar=ic.enabled)


@data_cli.command("list")
def cli_list() -> None:
    """Print information on the data stored in AIMBAT."""
    cli_data_print_table()


if __name__ == "__main__":
    data_cli(obj={})
