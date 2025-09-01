from aimbat.lib.common import ic
from aimbat.lib.typing import ProjectDefault
from aimbat.lib.defaults import get_default
from sqlmodel import Session
from urllib.request import urlopen
from io import BytesIO
from zipfile import ZipFile
import os
import shutil


def delete_sampledata(session: Session) -> None:
    """Delete sample data."""

    sampledata_dir = str(get_default(session, ProjectDefault.SAMPLEDATA_DIR))
    ic(sampledata_dir)
    shutil.rmtree(sampledata_dir)


def download_sampledata(session: Session, force: bool = False) -> None:
    """Download sample data."""

    ic()
    ic(force)

    sampledata_src = str(get_default(session, ProjectDefault.SAMPLEDATA_SRC))
    sampledata_dir = str(get_default(session, ProjectDefault.SAMPLEDATA_DIR))
    ic(sampledata_src, sampledata_dir)

    if os.path.exists(sampledata_dir) is True and len(os.listdir(sampledata_dir)) != 0:
        if force is True:
            delete_sampledata(session)
        else:
            raise RuntimeError(
                f"The directory {sampledata_dir} already exists and is non-empty."
            )

    with urlopen(sampledata_src) as zipresp:
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall(sampledata_dir)
