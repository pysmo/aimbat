"""The `io` module provides functions to read and write data files used with AIMBAT"""

from aimbat.lib.common import AimbatDataError
from aimbat.lib.db import engine
from aimbat.lib import models
from pysmo import SAC, Event, Seismogram, Station
from sqlmodel import Session, select
from datetime import datetime
import numpy as np


def _read_seismogram_sacdata_from_file(sacfile: str) -> np.ndarray:
    """Read seismogram data from a SAC file.

    Parameters:
        sacfile: str containing the name of the SAC file.

    Returns:
        Seismogram data.
    """

    return SAC.from_file(sacfile).seismogram.data


def _write_seismogram_sacdata_to_file(sacfile: str, data: np.ndarray) -> None:
    """Write seismogram data to a SAC file.

    Parameters:
        sacfile: str containing the name of the SAC file.
        data: Seismogram data.
    """

    sac = SAC.from_file(sacfile)
    sac.seismogram.data = data
    sac.write(sacfile)


def _read_metadata_from_sacfile(
    sacfile: str,
) -> tuple[Seismogram, Station, Event, datetime]:
    """Read seismogram metadata from a SAC file.

    Parameters:
        sacfile: str containing the name of the SAC file.

    Returns:
        Seismogram metadata.
    """
    sac = SAC.from_file(str(sacfile))
    if sac.timestamps.t0 is None:
        raise AimbatDataError("Unable to add {sacfile=}: header 'T0' contains no value")
    return sac.seismogram, sac.station, sac.event, sac.timestamps.t0


def read_seismogram_data_from_file(aimbatfile_id: int) -> np.ndarray:
    """Read seismogram data from a data file.

    Parameters:
        aimbatfile_id: ID of the datafile as stored in the AIMBAT database.

    Returns:
        Seismogram data.
    """
    with Session(engine) as session:
        select_aimbatfile = select(models.AimbatFile).where(
            models.AimbatFile.id == aimbatfile_id
        )
        aimbatfile = session.exec(select_aimbatfile).one()
        if aimbatfile.filetype == "sac":
            return _read_seismogram_sacdata_from_file(aimbatfile.filename)
    raise RuntimeError("Unable to read data from file")


def write_seismogram_data_to_file(aimbatfile_id: int, data: np.ndarray) -> None:
    """Write seismogram data to a data file.

    Parameters:
        aimbatfile_id: ID of the datafile as stored in the AIMBAT database
        data: Seismogram data
    """
    with Session(engine) as session:
        statement = select(models.AimbatFile).where(
            models.AimbatFile.id == aimbatfile_id
        )
        results = session.exec(statement).one()
        filetype, filename = results.filetype, results.filename
        if filetype == "sac":
            _write_seismogram_sacdata_to_file(filename, data)
        else:
            raise NotImplementedError(
                f"I don't know how to write data to file of type {filetype}"
            )


def read_metadata_from_file(
    filename: str, filetype: str
) -> tuple[Seismogram, Station, Event, datetime]:
    if filetype == "sac":
        return _read_metadata_from_sacfile(filename)
    raise NotImplementedError(f"Unable to parse files of type {filetype}")
