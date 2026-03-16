import os
import shutil
from io import BytesIO
from urllib.request import urlopen
from zipfile import ZipFile

from aimbat import settings
from aimbat.logger import logger

__all__ = ["delete_sampledata", "download_sampledata"]


def delete_sampledata() -> None:
    """Delete sample data."""

    logger.info(f"Deleting sample data in {settings.sampledata_dir}.")

    shutil.rmtree(settings.sampledata_dir)


def download_sampledata(force: bool = False) -> None:
    """Download sample data."""

    logger.info(
        f"Downloading sample data from {settings.sampledata_src} to {settings.sampledata_dir}."
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

    with urlopen(settings.sampledata_src) as zipresp:
        logger.debug(f"Extracting sample data to {settings.sampledata_dir}.")
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall(settings.sampledata_dir)

    logger.info("Sample data downloaded and extracted successfully.")
