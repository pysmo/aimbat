from aimbat.lib.defaults import get_default
from aimbat.lib.typing import ProjectDefault
from sqlmodel import Session
from urllib.request import urlopen
from io import BytesIO
from zipfile import ZipFile
from pathlib import Path
import os
import shutil


def delete_sampledata(session: Session) -> None:
    """Delete sample data."""

    sampledata_dir = Path(get_default(session, ProjectDefault.SAMPLEDATA_DIR))
    shutil.rmtree(sampledata_dir)


def download_sampledata(session: Session, force: bool = False) -> None:
    """Download sample data."""

    sampledata_src = str(get_default(session, ProjectDefault.SAMPLEDATA_SRC))
    sampledata_dir = Path(get_default(session, ProjectDefault.SAMPLEDATA_DIR))

    if sampledata_dir.exists() and len(os.listdir(sampledata_dir)) != 0:
        if force is True:
            delete_sampledata(session)
        else:
            raise FileExistsError(
                f"The directory {sampledata_dir} already exists and is non-empty."
            )

    with urlopen(sampledata_src) as zipresp:
        with ZipFile(BytesIO(zipresp.read())) as zfile:
            zfile.extractall(sampledata_dir)
