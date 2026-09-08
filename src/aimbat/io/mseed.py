"""miniSEED waveform I/O for AIMBAT.

Registers a reader and writer only - no station, event, or seismogram
creator. `pysmo.classes.MSeed` carries no station coordinates and no event
data, only channel identity, timing and samples, so there is nothing for a
creator to build a station or event from, and no pick concept to supply a
`t0` from either.

Scope boundary: this reader round-trips files AIMBAT itself wrote (e.g. via
`aimbat.core.add_seismograms_to_project`), it is not a general-purpose
miniSEED ingestion path. `MSeed.from_file` requires exactly one contiguous
segment and raises `ValueError` on a data gap or more than one channel.
Real-world archival or downloaded miniSEED is routinely multiplexed
(several channels in one file) and/or gappy (a channel split across
segments); reading that needs `MSeed.all_from_file` plus a policy for
picking, splitting, or merging segments, which this module does not
attempt. Such a file needs pre-processing (trimmed to one channel, one
contiguous segment) before it fits AIMBAT's one-file-one-seismogram model.

This module registers its capabilities with the I/O dispatch layer on
import, so importing it is sufficient to enable miniSEED support.
"""

from os import PathLike

import numpy as np
import numpy.typing as npt

from pysmo.classes import MSeed

from aimbat.logger import logger

from ._base import (
    SeismogramReadContext,
    file_source_present,
    seismogram_data_reader,
    seismogram_data_writer,
    source_probe,
)
from ._data import DataType

__all__ = [
    "mseed_source_present",
    "read_seismogram_data_from_mseedfile",
    "write_seismogram_data_to_mseedfile",
]


@source_probe(DataType.MSEED)
def mseed_source_present(context: SeismogramReadContext) -> bool:
    """Return whether the miniSEED file backing this seismogram still exists.

    A miniSEED file written by `add_seismograms_to_project` is created once and
    then treated exactly like any other external file, so a missing one is an
    ordinary prunable orphan.

    Args:
        context: Read context whose `sourcename` names the miniSEED file.

    Raises:
        SourceUnavailableError: If presence cannot be determined right now
            (an unreadable file, a missing parent directory, an unreachable
            mount).
    """
    return file_source_present(context.sourcename)


@seismogram_data_reader(DataType.MSEED)
def read_seismogram_data_from_mseedfile(
    context: SeismogramReadContext,
) -> npt.NDArray[np.floating]:
    """Read seismogram waveform data from a miniSEED file.

    Args:
        context: Read context whose `sourcename` names the miniSEED file.

    Returns:
        Seismogram amplitude data.

    Raises:
        ValueError: If the file holds zero, or more than one, contiguous
            segment (a data gap, or more than one channel) - see the
            module docstring's scope boundary.
    """

    logger.debug(f"Reading seismogram data from {context.sourcename}.")

    return MSeed.from_file(context.sourcename).data


@seismogram_data_writer(DataType.MSEED)
def write_seismogram_data_to_mseedfile(
    mseedfile: str | PathLike[str], data: npt.NDArray[np.floating]
) -> None:
    """Write seismogram waveform data to a miniSEED file.

    Args:
        mseedfile: Name of the miniSEED file.
        data: Seismogram amplitude data to write.
    """

    logger.debug(f"Writing seismogram data to {mseedfile}.")

    mseed = MSeed.from_file(mseedfile)
    mseed.data = data
    mseed.write(mseedfile)
