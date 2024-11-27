"""The `io` module provides functions to read and write data files used with AIMBAT"""

from aimbat.lib.common import AimbatDataError, ic
from pysmo import SAC, Event, Seismogram, Station
from aimbat.lib.types import ProjectDefault
from datetime import datetime
from sqlmodel import Session
import numpy as np
import numpy.typing as npt


def _read_seismogram_data_from_sacfile(sacfile: str) -> npt.NDArray[np.float64]:
    """Read seismogram data from a SAC file.

    Parameters:
        sacfile: str containing the name of the SAC file.

    Returns:
        Seismogram data.
    """

    ic()

    return SAC.from_file(sacfile).seismogram.data


def _write_seismogram_data_to_sacfile(
    sacfile: str, data: npt.NDArray[np.float64]
) -> None:
    """Write seismogram data to a SAC file.

    Parameters:
        sacfile: str containing the name of the SAC file.
        data: Seismogram data.
    """

    ic()
    ic(sacfile, data)

    sac = SAC.from_file(sacfile)
    sac.seismogram.data = data
    sac.write(sacfile)


def _read_metadata_from_sacfile(
    session: Session,
    sacfile: str,
) -> tuple[Seismogram, Station, Event, datetime]:
    """Read seismogram metadata from a SAC file.

    Parameters:
        session: Database session.
        sacfile: Name of the SAC file.

    Returns:
        Seismogram metadata.
    """
    from aimbat.lib.defaults import get_default

    ic()
    ic(sacfile)

    initial_pick_header = get_default(session, ProjectDefault.INITIAL_PICK_HEADER)
    sac = SAC.from_file(str(sacfile))
    t0 = getattr(sac.timestamps, str(initial_pick_header))
    if t0 is None:
        raise AimbatDataError(
            "Unable to add {sacfile=}: header '{initial_pick_header}' contains no value"
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

    ic()
    ic(filename, filetype)

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
    """

    ic()
    ic(filename, filetype, data)

    if filetype == "sac":
        _write_seismogram_data_to_sacfile(filename, data)
    else:
        raise NotImplementedError(
            f"I don't know how to write data to file of type {filetype}"
        )


def read_metadata_from_file(
    session: Session, filename: str, filetype: str
) -> tuple[Seismogram, Station, Event, datetime]:
    """Read seismogram metadata from a seismogram file.

    Parameters:
        session: Database session.
        filename: Input filename.
        filetype: Type of input file.
    """

    ic()
    ic(filename, filetype)

    if filetype == "sac":
        return _read_metadata_from_sacfile(session, filename)
    raise NotImplementedError(f"Unable to parse files of type {filetype}")
