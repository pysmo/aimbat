#!/usr/bin/env python

import click
import os
import shutil
from io import BytesIO
from urllib.request import urlopen
from zipfile import ZipFile
from pysmo.aimbat.lib.defaults import AimbatDefaults

_DEFAULTS = AimbatDefaults()
_SAMPLEDATA_DIRECTORY = _DEFAULTS.sampledata_dir.value
_SAMPLEDATA_SOURCE = _DEFAULTS.sampledata_src.value


@click.command('sampledata')
@click.option('-d', '--directory', 'target_directory', default=_SAMPLEDATA_DIRECTORY, show_default=True,
              help="Target directory where sample data are stored.")
@click.option('-u', '--url', default=_SAMPLEDATA_SOURCE, show_default=True,
              help="Download sample data from here (must be a zip file).")
@click.option('-r', '--rm', 'remove', is_flag=True, help="Remove sample data directory and its contents")
@click.option('-f', '--force', is_flag=True,
              help="Remove target directory if it already exists and re-download sample data.")
def cli(target_directory, url, remove, force):
    """
    Download aimbat sample data and save it to a folder.
    """
    if remove is True:
        remove_sample_data(target_directory)
    else:
        download_sample_data(target_directory, url, force)


def remove_sample_data(target_directory=_SAMPLEDATA_DIRECTORY):
    """
    Recursively delete sample data directory.
    """
    shutil.rmtree(target_directory, ignore_errors=False, onerror=None)


def download_sample_data(target_directory=_SAMPLEDATA_DIRECTORY, url=_SAMPLEDATA_SOURCE, force=False):
    """
    Download aimbat sample data and save it to a folder.
    """
    if os.path.exists(target_directory) is True:
        if force is True:
            remove_sample_data(target_directory)
        else:
            raise RuntimeError(f"The directory {target_directory} already exists.")
    with urlopen(url) as zipresp:
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall(target_directory)


if __name__ == "__main__":
    cli()
