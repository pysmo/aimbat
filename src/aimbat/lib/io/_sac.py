from __future__ import annotations
from aimbat.config import settings
from aimbat.logger import logger
from pysmo.classes import SAC
from os import PathLike
from functools import partial
import numpy as np
import numpy.typing as npt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aimbat.lib.models import AimbatEvent, AimbatSeismogram, AimbatStation


def read_seismogram_data_from_sacfile(
    sacfile: str | PathLike,
) -> npt.NDArray[np.float64]:
    """Read seismogram data from a SAC file.

    Args:
        sacfile: Name of the SAC file.

    Returns:
        Seismogram data.
    """

    logger.debug(f"Reading seismogram data from {sacfile}.")

    return SAC.from_file(sacfile).seismogram.data


def write_seismogram_data_to_sacfile(
    sacfile: str | PathLike, data: npt.NDArray[np.float64]
) -> None:
    """Write seismogram data to a SAC file.

    Args:
        sacfile: Name of the SAC file.
        data: Seismogram data.
    """

    logger.debug(f"Writing seismogram data to {sacfile}.")

    sac = SAC.from_file(sacfile)
    sac.seismogram.data = data
    sac.write(sacfile)


def create_station_from_sacfile(sacfile: str | PathLike) -> AimbatStation:
    """Create an AimbatStation instance from a SAC file.

    Args:
        sacfile: Name of the SAC file.

    Returns:
        A new AimbatStation instance.
    """

    from aimbat.lib.models import AimbatStation

    logger.debug(f"Reading station data from {sacfile}.")

    station = SAC.from_file(sacfile).station
    aimbat_station = AimbatStation.model_validate(station)
    return aimbat_station


def create_event_from_sacfile(sacfile: str | PathLike) -> AimbatEvent:
    """Create an AimbatSeismogram instance from a SAC file.

    Args:
        sacfile: Name of the SAC file.
    """

    from aimbat.lib.models import AimbatEvent, AimbatEventParameters

    logger.debug(f"Reading event data from {sacfile}.")

    event = SAC.from_file(sacfile).event
    aimbat_event = AimbatEvent.model_validate(
        event, update={"parameters": AimbatEventParameters()}
    )
    return aimbat_event


def create_seismogram_from_sacfile_and_pick_header(
    sacfile: str | PathLike, sac_pick_header: str
) -> AimbatSeismogram:
    """Create an AimbatSeismogram instance from a SAC file.

    Args:
        sacfile: Name of the SAC file.
        sac_pick_header: SAC header to use as t0 in AIMBAT.
    """

    from aimbat.lib.models import AimbatSeismogram, AimbatSeismogramParameters

    logger.debug(f"Reading seismogram metadata from {sacfile}.")

    sac = SAC.from_file(sacfile)
    t0 = getattr(sac.timestamps, sac_pick_header)
    seismogram = sac.seismogram
    aimbat_seismogram = AimbatSeismogram.model_validate(
        seismogram, update={"t0": t0, "parameters": AimbatSeismogramParameters()}
    )
    return aimbat_seismogram


create_seismogram_from_sacfile = partial(
    create_seismogram_from_sacfile_and_pick_header,
    sac_pick_header=settings.sac_pick_header,
)
