"""SAC file I/O for AIMBAT.

Reads and writes seismogram data from SAC files via `pysmo`, and creates
`AimbatStation`, `AimbatEvent`, and `AimbatSeismogram` model instances from
SAC file metadata.

This module registers its capabilities with the I/O dispatch layer on import,
so importing it is sufficient to enable SAC support.
"""

from __future__ import annotations

from os import PathLike
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from pysmo.classes import SAC

from aimbat import settings
from aimbat.logger import logger

from ._base import (
    SeismogramReadContext,
    SourceRecords,
    SourceRecordsRequest,
    event_creator,
    file_source_present,
    seismogram_creator,
    seismogram_data_reader,
    seismogram_data_writer,
    source_probe,
    source_records_reader,
    station_creator,
)
from ._data import DataType

if TYPE_CHECKING:
    from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatStation

__all__ = [
    "create_event_from_sacfile",
    "create_seismogram_from_sacfile",
    "create_seismogram_from_sacfile_and_pick_header",
    "create_station_from_sacfile",
    "read_records_from_sacfile",
    "read_seismogram_data_from_sacfile",
    "sac_source_present",
    "write_seismogram_data_to_sacfile",
]


@source_probe(DataType.SAC)
def sac_source_present(context: SeismogramReadContext) -> bool:
    """Return whether the SAC file backing this seismogram still exists.

    Args:
        context: Read context whose `sourcename` names the SAC file.

    Raises:
        SourceUnavailableError: If presence cannot be determined right now
            (an unreadable file, a missing parent directory, an unreachable
            mount).
    """
    return file_source_present(context.sourcename)


@seismogram_data_reader(DataType.SAC)
def read_seismogram_data_from_sacfile(
    context: SeismogramReadContext,
) -> npt.NDArray[np.floating]:
    """Read seismogram waveform data from a SAC file.

    Args:
        context: Read context whose `sourcename` names the SAC file.

    Returns:
        Seismogram amplitude data.
    """

    logger.debug(f"Reading seismogram data from {context.sourcename}.")

    return SAC.from_file(context.sourcename).seismogram.data


@seismogram_data_writer(DataType.SAC)
def write_seismogram_data_to_sacfile(
    sacfile: str | PathLike[str], data: npt.NDArray[np.floating]
) -> None:
    """Write seismogram waveform data to a SAC file.

    Args:
        sacfile: Name of the SAC file.
        data: Seismogram amplitude data to write.
    """

    logger.debug(f"Writing seismogram data to {sacfile}.")

    sac = SAC.from_file(sacfile)
    sac.seismogram.data = data
    sac.write(sacfile)


def _station_from_sac(sac: SAC) -> AimbatStation:
    """Build an `AimbatStation` from an already-read SAC file."""

    from aimbat.models import AimbatStation

    return AimbatStation.model_validate(sac.station)


def _event_from_sac(sac: SAC) -> AimbatEvent:
    """Build an `AimbatEvent` from an already-read SAC file."""

    from aimbat.models import AimbatEvent, AimbatEventParameters

    return AimbatEvent.model_validate(
        sac.event, update={"parameters": AimbatEventParameters()}
    )


def _seismogram_from_sac(sac: SAC, sac_pick_header: str) -> AimbatSeismogram:
    """Build an `AimbatSeismogram` from an already-read SAC file.

    Raises:
        ValueError: If `sac_pick_header` is not a SAC pick header, or if the
            file has no pick stored in it.
    """

    from aimbat.models import AimbatSeismogram, AimbatSeismogramParameters

    if not hasattr(sac.timestamps, sac_pick_header):
        raise ValueError(
            f"{sac_pick_header!r} is not a SAC pick header. Point the "
            + "sac_pick_header setting (AIMBAT_SAC_PICK_HEADER) at one that is."
        )
    t0 = getattr(sac.timestamps, sac_pick_header)
    if t0 is None:
        raise ValueError(
            f"No initial pick found in SAC header {sac_pick_header!r}. Either add "
            + "the pick, or point the sac_pick_header setting "
            + "(AIMBAT_SAC_PICK_HEADER) at a header that has one."
        )
    return AimbatSeismogram.model_validate(
        sac.seismogram, update={"t0": t0, "parameters": AimbatSeismogramParameters()}
    )


@source_records_reader(DataType.SAC)
def read_records_from_sacfile(request: SourceRecordsRequest) -> SourceRecords:
    """Build every record a request asks for from one read of a SAC file.

    Args:
        request: The records wanted, and the SAC file to build them from.

    Returns:
        The requested records.

    Raises:
        ValueError: If a seismogram is wanted and the configured
            `sac_pick_header` is not a SAC pick header, or the file has no
            pick stored in it.
    """

    logger.debug(f"Reading records from {request.sourcename}.")

    sac = SAC.from_file(request.sourcename)
    return SourceRecords(
        station=_station_from_sac(sac) if request.station else None,
        event=_event_from_sac(sac) if request.event else None,
        seismogram=(
            _seismogram_from_sac(sac, settings.sac_pick_header)
            if request.seismogram
            else None
        ),
    )


@station_creator(DataType.SAC)
def create_station_from_sacfile(sacfile: str | PathLike[str]) -> AimbatStation:
    """Create an `AimbatStation` instance from a SAC file.

    Args:
        sacfile: Name of the SAC file.

    Returns:
        A new `AimbatStation` instance.
    """

    logger.debug(f"Reading station data from {sacfile}.")

    return _station_from_sac(SAC.from_file(sacfile))


@event_creator(DataType.SAC)
def create_event_from_sacfile(sacfile: str | PathLike[str]) -> AimbatEvent:
    """Create an `AimbatEvent` instance from a SAC file.

    Args:
        sacfile: Name of the SAC file.

    Returns:
        A new `AimbatEvent` instance.
    """

    logger.debug(f"Reading event data from {sacfile}.")

    return _event_from_sac(SAC.from_file(sacfile))


def create_seismogram_from_sacfile_and_pick_header(
    sacfile: str | PathLike[str], sac_pick_header: str
) -> AimbatSeismogram:
    """Create an `AimbatSeismogram` instance from a SAC file.

    Args:
        sacfile: Name of the SAC file.
        sac_pick_header: SAC header to use as t0 in AIMBAT.

    Returns:
        A new `AimbatSeismogram` instance, with `t0` set from `sac_pick_header`.

    Raises:
        ValueError: If `sac_pick_header` is not a SAC pick header, or if the
            file has no pick stored in it.
    """

    logger.debug(f"Reading seismogram metadata from {sacfile}.")

    return _seismogram_from_sac(SAC.from_file(sacfile), sac_pick_header)


@seismogram_creator(DataType.SAC)
def create_seismogram_from_sacfile(sacfile: str | PathLike[str]) -> AimbatSeismogram:
    """Create an `AimbatSeismogram` instance from a SAC file, using the configured pick header.

    Args:
        sacfile: Name of the SAC file.

    Returns:
        A new `AimbatSeismogram` instance.
    """
    return create_seismogram_from_sacfile_and_pick_header(
        sacfile, settings.sac_pick_header
    )
