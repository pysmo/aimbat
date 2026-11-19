"""SAC file I/O for AIMBAT.

Reads and writes seismogram data from SAC files via `pysmo`, creates
`AimbatStation`, `AimbatEvent`, and `AimbatSeismogram` model instances from
SAC file metadata, and reads the picks stored in the `a` and `t0`-`t9`
headers together with their `ka` and `kt0`-`kt9` labels.

This module registers its capabilities with the I/O dispatch layer on import,
so importing it is sufficient to enable SAC support.
"""

from __future__ import annotations

from os import PathLike
from typing import TYPE_CHECKING, Final

import numpy as np
import numpy.typing as npt

from pysmo.classes import SAC

from aimbat.logger import logger

from ._base import (
    SeismogramReadContext,
    SourcePick,
    SourceRecords,
    SourceRecordsRequest,
    event_creator,
    file_source_present,
    pick_reader,
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
    "create_station_from_sacfile",
    "read_picks_from_sacfile",
    "read_records_from_sacfile",
    "read_seismogram_data_from_sacfile",
    "sac_source_present",
    "write_seismogram_data_to_sacfile",
]

_SAC_PICK_HEADERS: Final = ("a", *(f"t{i}" for i in range(10)))


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

    from aimbat.models import AimbatEvent

    return AimbatEvent.model_validate(sac.event)


def _seismogram_from_sac(sac: SAC) -> AimbatSeismogram:
    """Build an `AimbatSeismogram` from an already-read SAC file."""

    from aimbat.models import AimbatSeismogram

    return AimbatSeismogram.model_validate(sac.seismogram)


def _picks_from_sac(sac: SAC) -> tuple[SourcePick, ...]:
    """Return the picks of an already-read SAC file.

    Each pick header (`a`, `t0`-`t9`) that holds a time gives one pick, keyed
    by the header name and labelled from its label header (`ka`, `kt0`-`kt9`).
    A label without a time gives no pick.
    """

    picks = []
    for header in _SAC_PICK_HEADERS:
        time = getattr(sac.timestamps, header)
        if time is None:
            continue
        label = getattr(sac.native, f"k{header}")
        picks.append(SourcePick(time=time, key=header, label=label))
    return tuple(picks)


@pick_reader(DataType.SAC)
def read_picks_from_sacfile(sacfile: str | PathLike[str]) -> tuple[SourcePick, ...]:
    """Read the picks stored in a SAC file.

    Args:
        sacfile: Name of the SAC file.

    Returns:
        One pick for each of the `a` and `t0`-`t9` headers that holds a time,
            labelled from the matching `ka` or `kt0`-`kt9` header.
    """

    logger.debug(f"Reading picks from {sacfile}.")

    return _picks_from_sac(SAC.from_file(sacfile))


@source_records_reader(DataType.SAC)
def read_records_from_sacfile(request: SourceRecordsRequest) -> SourceRecords:
    """Build every record a request asks for from one read of a SAC file.

    Args:
        request: The records wanted, and the SAC file to build them from.

    Returns:
        The requested records. The end time of the seismogram is included
            when a seismogram or picks are asked for.
    """

    logger.debug(f"Reading records from {request.sourcename}.")

    sac = SAC.from_file(request.sourcename)
    return SourceRecords(
        station=_station_from_sac(sac) if request.station else None,
        event=_event_from_sac(sac) if request.event else None,
        seismogram=_seismogram_from_sac(sac) if request.seismogram else None,
        seismogram_end_time=(
            sac.seismogram.end_time if request.seismogram or request.picks else None
        ),
        picks=_picks_from_sac(sac) if request.picks else (),
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


@seismogram_creator(DataType.SAC)
def create_seismogram_from_sacfile(sacfile: str | PathLike[str]) -> AimbatSeismogram:
    """Create an `AimbatSeismogram` instance from a SAC file.

    Args:
        sacfile: Name of the SAC file.

    Returns:
        A new `AimbatSeismogram` instance.
    """

    logger.debug(f"Reading seismogram metadata from {sacfile}.")

    return _seismogram_from_sac(SAC.from_file(sacfile))
