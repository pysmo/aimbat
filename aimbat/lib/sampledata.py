from aimbat.lib.common import ic
from aimbat.lib.defaults import defaults_get_value
from urllib.request import urlopen
from io import BytesIO
from zipfile import ZipFile
import os
import shutil


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
