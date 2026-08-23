"""Download and remove the bundled AIMBAT sample dataset."""

import os
import shutil
from io import BytesIO
from urllib.request import urlopen
from zipfile import ZipFile

from aimbat import settings
from aimbat.logger import logger

__all__ = ["delete_sampledata", "download_sampledata"]

_SAMPLEDATA_SRC = (
    "https://github.com/pysmo/aimbat-sampledata/archive/refs/heads/master.zip"
)


def delete_sampledata() -> None:
    """Delete the sample data directory (`Settings.sampledata_dir`) and its contents."""

    logger.info(f"Deleting sample data in {settings.sampledata_dir}.")

    shutil.rmtree(settings.sampledata_dir)


def download_sampledata(force: bool = False) -> None:
    """Download and extract the AIMBAT sample dataset.

    Downloads the sample data archive and extracts it into
    `Settings.sampledata_dir`.

    Args:
        force: Delete and replace an existing non-empty sample data
            directory instead of raising an error.

    Raises:
        FileExistsError: If the sample data directory already exists and is
            non-empty, and `force` is False.
    """

    logger.info(
        f"Downloading sample data from {_SAMPLEDATA_SRC} to {settings.sampledata_dir}."
    )

    if (
        settings.sampledata_dir.exists()
        and len(os.listdir(settings.sampledata_dir)) != 0
    ):
        if force is True:
            delete_sampledata()
        else:
            raise FileExistsError(
                f"The directory {settings.sampledata_dir} already exists and is non-empty."
            )

    with urlopen(_SAMPLEDATA_SRC) as zipresp:
        logger.debug(f"Extracting sample data to {settings.sampledata_dir}.")
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall(settings.sampledata_dir)

    logger.info("Sample data downloaded and extracted successfully.")
