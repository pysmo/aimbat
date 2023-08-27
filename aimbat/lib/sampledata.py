from aimbat.lib.defaults import defaults_get_value
from aimbat.lib.db import db_engine
from urllib.request import urlopen
from io import BytesIO
from zipfile import ZipFile
import click
import os
import shutil

ENGINE = db_engine()


def sampledata_delete(engine):   # type: ignore
    """Delete sample data."""

    sampledata_dir = str(defaults_get_value(engine, "sampledata_dir"))
    shutil.rmtree(sampledata_dir, ignore_errors=False, onerror=None)


def sampledata_download(engine,  # type: ignore
                        force: bool = False) -> None:
    """Download sample data."""

    sampledata_src = str(defaults_get_value(engine, "sampledata_src"))
    sampledata_dir = str(defaults_get_value(engine, "sampledata_dir"))

    if os.path.exists(sampledata_dir) is True:
        if force is True:
            sampledata_delete(engine)
        else:
            raise RuntimeError(f"The directory {sampledata_dir} already exists.")

    with urlopen(sampledata_src) as zipresp:
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall(sampledata_dir)


@click.group("sampledata")
def cli() -> None:
    """Download aimbat sample data and save it to a folder.

    The sample data source url can be viewed or changed via `aimbat default
    <list/set> sampledata_src`. Likewise the sample data destination folder
    be viewed or changed via `aimbat default <list/set> sampledata_dir`."""
    pass


@cli.command("delete")
def sampledata_cli_delete() -> None:
    """Recursively delete sample data directory."""

    sampledata_delete(ENGINE)


@cli.command("download")
@click.option('-f', '--force', is_flag=True,
              help="Remove target directory if it already exists and re-download sample data.")
def sampledata_cli_download(force: bool) -> None:
    """Download aimbat sample data."""

    sampledata_download(ENGINE, force)


if __name__ == "__main__":
    cli()
