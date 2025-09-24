from urllib.request import urlopen
from io import BytesIO
from zipfile import ZipFile
from pathlib import Path
import aimbat.lib.defaults as defaults
import os
import shutil


def delete_sampledata() -> None:
    """Delete sample data."""

    sampledata_dir = Path(defaults.AIMBAT_SAMPLEDATA_DIR)
    shutil.rmtree(sampledata_dir)


def download_sampledata(force: bool = False) -> None:
    """Download sample data."""

    sampledata_src = defaults.AIMBAT_SAMPLEDATA_SRC
    sampledata_dir = Path(defaults.AIMBAT_SAMPLEDATA_DIR)

    if sampledata_dir.exists() and len(os.listdir(sampledata_dir)) != 0:
        if force is True:
            delete_sampledata()
        else:
            raise FileExistsError(
                f"The directory {sampledata_dir} already exists and is non-empty."
            )

    with urlopen(sampledata_src) as zipresp:
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall(sampledata_dir)
