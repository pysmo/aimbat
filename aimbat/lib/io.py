"""Functions to read and write data files used with AIMBAT"""

from aimbat.lib.common import logger
from pysmo import Event, Seismogram, Station
from pysmo.classes import SAC
from datetime import datetime
from sqlmodel import Session
import aimbat.lib.defaults as defaults
import os
import numpy as np
import numpy.typing as npt


def _read_seismogram_data_from_sacfile(sacfile: str) -> npt.NDArray[np.float64]:
    """Read seismogram data from a SAC file.

    Parameters:
        sacfile: str containing the name of the SAC file.

    Returns:
        Seismogram data.
    """

    logger.debug(f"Reading seismogram data from {sacfile}.")

    return SAC.from_file(sacfile).seismogram.data


def _write_seismogram_data_to_sacfile(
    sacfile: str, data: npt.NDArray[np.float64]
) -> None:
    """Write seismogram data to a SAC file.

    Parameters:
        sacfile: str containing the name of the SAC file.
        data: Seismogram data.
    """

    logger.debug(f"Writing seismogram data to {sacfile}.")

    sac = SAC.from_file(sacfile)
    sac.seismogram.data = data
    sac.write(sacfile)


def _read_metadata_from_sacfile(
    session: Session,
    sacfile: str | os.PathLike,
) -> tuple[Seismogram, Station, Event, datetime]:
    """Read seismogram metadata from a SAC file.

    Parameters:
        session: Database session.
        sacfile: Name of the SAC file.

    Returns:
        Seismogram metadata.

    Raises:
        TypeError: If the initial pick header is NoneType.
    """

    logger.debug(f"Reading seismogram metadata from {sacfile}.")

    initial_pick_header = defaults.AIMBAT_SAC_PICK_HEADER
    logger.debug(f"Using SAC header {initial_pick_header} as t0.")
    sac = SAC.from_file(str(sacfile))
    t0 = getattr(sac.timestamps, initial_pick_header)
    if t0 is None:
        raise TypeError(
            "Unable to get {sacfile=}: header '{initial_pick_header}' is NoneType"
        )
    return sac.seismogram, sac.station, sac.event, t0


def read_seismogram_data_from_file(
    filename: str, filetype: str
) -> npt.NDArray[np.float64]:
    """Read seismogram data from a data file.

    Parameters:
        filename: Name of the seismogram file.
        filetype: AIMBAT compatible filetype.

    Returns:
        Seismogram data.
    """

    logger.debug(f"Reading seismogram data from {filename}.")

    if filetype == "sac":
        return _read_seismogram_data_from_sacfile(filename)
    raise RuntimeError("Unable to read data from file")


def write_seismogram_data_to_file(
    filename: str, filetype: str, data: npt.NDArray[np.float64]
) -> None:
    """Write seismogram data to a data file.

    Parameters:
        filename: Name of the seismogram file.
        filetype: AIMBAT compatible filetype.
        data: Seismogram data

    Raises:
        NotImplementedError: If the filetype is not supported.
    """

    logger.debug(f"Writing seismogram data to {filename}.")

    if filetype == "sac":
        _write_seismogram_data_to_sacfile(filename, data)
    else:
        raise NotImplementedError(
            f"I don't know how to write data to file of type {filetype}"
        )


def read_metadata_from_file(
    session: Session, filename: str | os.PathLike, filetype: str
) -> tuple[Seismogram, Station, Event, datetime]:
    """Read seismogram metadata from a seismogram file.

    Parameters:
        session: Database session.
        filename: Input filename.
        filetype: Type of input file.

    Raises:
        NotImplementedError: If the filetype is not supported.
    """

    logger.debug(f"Reading seismogram metadata from {filename}.")

    if filetype == "sac":
        return _read_metadata_from_sacfile(session, filename)
    raise NotImplementedError(f"Unable to parse files of type {filetype}")
