from aimbat.lib.defaults import defaults_get_value
from aimbat.lib.common import cli_enable_debug
from urllib.request import urlopen
from io import BytesIO
from zipfile import ZipFile
from icecream import ic  # type: ignore
import click
import os
import shutil


ic.disable()


def sampledata_delete() -> None:
    """Delete sample data."""

    sampledata_dir = str(defaults_get_value("sampledata_dir"))
    ic(sampledata_dir)
    shutil.rmtree(sampledata_dir)


def sampledata_download(force: bool = False) -> None:
    """Download sample data."""

    ic()
    ic(force)

    sampledata_src = str(defaults_get_value("sampledata_src"))
    sampledata_dir = str(defaults_get_value("sampledata_dir"))
    ic(sampledata_src, sampledata_dir)

    if os.path.exists(sampledata_dir) is True and len(os.listdir(sampledata_dir)) != 0:
        if force is True:
            sampledata_delete()
        else:
            raise RuntimeError(
                f"The directory {sampledata_dir} already exists and is non-empty."
            )

    with urlopen(sampledata_src) as zipresp:
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall(sampledata_dir)


@click.group("sampledata")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Download aimbat sample data and save it to a folder.

    The sample data source url can be viewed or changed via `aimbat default
    <list/set> sampledata_src`. Likewise the sample data destination folder
    be viewed or changed via `aimbat default <list/set> sampledata_dir`."""
    cli_enable_debug(ctx)


@cli.command("delete")
def sampledata_cli_delete() -> None:
    """Recursively delete sample data directory."""

    sampledata_delete()


@cli.command("download")
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Remove target directory if it already exists and re-download sample data.",
)
def sampledata_cli_download(force: bool) -> None:
    """Download aimbat sample data."""

    sampledata_download(force)


if __name__ == "__main__":
    cli(obj={})
