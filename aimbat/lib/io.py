"""The `io` module provides functions to read and write data files used with AIMBAT"""

from aimbat.lib.common import AimbatDataError
import aimbat.lib.defaults as defaults
from pysmo import SAC, Event, Seismogram, Station
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
    initial_pick_header = defaults.defaults_get_value("initial_pick_header")
    sac = SAC.from_file(str(sacfile))
    t0 = getattr(sac.timestamps, str(initial_pick_header))
    if t0 is None:
        raise AimbatDataError(
            "Unable to add {sacfile=}: header '{initial_pick_header}' contains no value"
        )
    return sac.seismogram, sac.station, sac.event, t0


def read_seismogram_data_from_file(filename: str, filetype: str) -> np.ndarray:
    """Read seismogram data from a data file.

    Parameters:
        aimbatfile_id: ID of the datafile as stored in the AIMBAT database.

    Returns:
        Seismogram data.
    """
    if filetype == "sac":
        return _read_seismogram_sacdata_from_file(filename)
    raise RuntimeError("Unable to read data from file")


def write_seismogram_data_to_file(
    filename: str, filetype: str, data: np.ndarray
) -> None:
    """Write seismogram data to a data file.

    Parameters:
        aimbatfile: instance of an AimbatFile
        data: Seismogram data
    """
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
