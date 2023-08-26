from ..lib.defaults import defaults_get_value
from ..lib.project import project_db_engine
from urllib.request import urlopen
from io import BytesIO
from zipfile import ZipFile
import click
import os
import shutil

engine = project_db_engine()


def delete_data(sampledata_dir: str) -> None:
    shutil.rmtree(sampledata_dir, ignore_errors=False, onerror=None)


@click.group("sampledata")
def cli() -> None:
    """Download aimbat sample data and save it to a folder.

    The sample data source url can be viewed or changed via `aimbat default
    <list/set> sampledata_src`. Likewise the sample data destination folder
    be viewed or changed via `aimbat default <list/set> sampledata_dir`."""
    pass


@cli.command("delete")
def remove_sample_data() -> None:
    """Recursively delete sample data directory."""

    sampledata_dir = str(defaults_get_value(engine, "sampledata_dir"))
    delete_data(sampledata_dir)


@cli.command("download")
@click.option('-f', '--force', is_flag=True,
              help="Remove target directory if it already exists and re-download sample data.")
def download_sample_data(force: bool) -> None:
    """Download aimbat sample data."""

    sampledata_dir = str(defaults_get_value(engine, "sampledata_dir"))
    sampledata_src = str(defaults_get_value(engine, "sampledata_src"))
    if os.path.exists(sampledata_dir) is True:
        if force is True:
            delete_data(sampledata_dir)
        else:
            raise RuntimeError(f"The directory {sampledata_dir} already exists.")
    with urlopen(sampledata_src) as zipresp:
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall(sampledata_dir)


if __name__ == "__main__":
    cli()
