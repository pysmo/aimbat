"""Public I/O interface for AIMBAT data sources.

Data source modules register their capabilities using the `register_*`
functions. Not all data sources need to support all capabilities — for example,
a source providing waveform data only would register
`register_seismogram_data_reader` and `register_seismogram_data_writer` but
not the creator functions.

The SAC data source (`aimbat.io._sac`) registers its capabilities
automatically when imported.
"""

from __future__ import annotations
from aimbat.aimbat_types import DataType
from aimbat.logger import logger
from os import PathLike
from typing import TYPE_CHECKING, Callable
import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from aimbat.models import (
        AimbatEvent,
        AimbatSeismogram,
        AimbatStation,
    )


__all__ = [
    "clear_seismogram_cache",
    "create_event",
    "create_seismogram",
    "create_station",
    "read_seismogram_data",
    "register_event_creator",
    "register_seismogram_creator",
    "register_seismogram_data_reader",
    "register_seismogram_data_writer",
    "register_station_creator",
    "supports_event_creation",
    "supports_seismogram_creation",
    "supports_seismogram_data_reading",
    "supports_seismogram_data_writing",
    "supports_station_creation",
    "write_seismogram_data",
]

_cache: dict[tuple[str, DataType], npt.NDArray[np.float64]] = {}

# Per-capability registries — populated by data source modules (e.g. _sac)
_station_creators: dict[DataType, Callable[[str | PathLike], AimbatStation]] = {}
_event_creators: dict[DataType, Callable[[str | PathLike], AimbatEvent]] = {}
_seismogram_creators: dict[DataType, Callable[[str | PathLike], AimbatSeismogram]] = {}
_seismogram_data_readers: dict[
    DataType, Callable[[str | PathLike], npt.NDArray[np.float64]]
] = {}
_seismogram_data_writers: dict[
    DataType, Callable[[str | PathLike, npt.NDArray[np.float64]], None]
] = {}


def register_station_creator(
    datatype: DataType,
    fn: Callable[[str | PathLike], AimbatStation],
) -> None:
    """Register a function that creates an `AimbatStation` from a data source.

    Args:
        datatype: The data type this creator handles.
        fn: Callable that accepts a datasource path or name and returns an
            `AimbatStation` instance.
    """
    _station_creators[datatype] = fn


def register_event_creator(
    datatype: DataType,
    fn: Callable[[str | PathLike], AimbatEvent],
) -> None:
    """Register a function that creates an `AimbatEvent` from a data source.

    Args:
        datatype: The data type this creator handles.
        fn: Callable that accepts a datasource path or name and returns an
            `AimbatEvent` instance.
    """
    _event_creators[datatype] = fn


def register_seismogram_creator(
    datatype: DataType,
    fn: Callable[[str | PathLike], AimbatSeismogram],
) -> None:
    """Register a function that creates an `AimbatSeismogram` from a data source.

    Args:
        datatype: The data type this creator handles.
        fn: Callable that accepts a datasource path or name and returns an
            `AimbatSeismogram` instance.
    """
    _seismogram_creators[datatype] = fn


def register_seismogram_data_reader(
    datatype: DataType,
    fn: Callable[[str | PathLike], npt.NDArray[np.float64]],
) -> None:
    """Register a function that reads seismogram waveform data from a data source.

    Args:
        datatype: The data type this reader handles.
        fn: Callable that accepts a datasource path or name and returns the
            waveform data as a NumPy array.
    """
    _seismogram_data_readers[datatype] = fn


def register_seismogram_data_writer(
    datatype: DataType,
    fn: Callable[[str | PathLike, npt.NDArray[np.float64]], None],
) -> None:
    """Register a function that writes seismogram waveform data to a data source.

    Args:
        datatype: The data type this writer handles.
        fn: Callable that accepts a datasource path or name and a NumPy array,
            and writes the data to the source.
    """
    _seismogram_data_writers[datatype] = fn


def supports_station_creation(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered station creator."""
    return datatype in _station_creators


def supports_event_creation(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered event creator."""
    return datatype in _event_creators


def supports_seismogram_creation(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered seismogram creator."""
    return datatype in _seismogram_creators


def supports_seismogram_data_reading(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered seismogram data reader."""
    return datatype in _seismogram_data_readers


def supports_seismogram_data_writing(datatype: DataType) -> bool:
    """Return whether `datatype` has a registered seismogram data writer."""
    return datatype in _seismogram_data_writers


def clear_seismogram_cache() -> None:
    """Clear the in-memory seismogram data cache."""
    _cache.clear()


def create_station(datasource: str | PathLike, datatype: DataType) -> AimbatStation:
    """Create an `AimbatStation` from a data source.

    Args:
        datasource: Data source path or name.
        datatype: Data type of the source.

    Returns:
        A new `AimbatStation` instance.

    Raises:
        NotImplementedError: If `datatype` has no registered station creator.
    """
    logger.debug(f"Creating AimbatStation from {datasource}.")
    creator = _station_creators.get(datatype)
    if creator is None:
        raise NotImplementedError(f"{datatype} does not support station creation.")
    return creator(datasource)


def create_event(datasource: str | PathLike, datatype: DataType) -> AimbatEvent:
    """Create an `AimbatEvent` from a data source.

    Args:
        datasource: Data source path or name.
        datatype: Data type of the source.

    Returns:
        A new `AimbatEvent` instance.

    Raises:
        NotImplementedError: If `datatype` has no registered event creator.
    """
    logger.debug(f"Creating AimbatEvent from {datasource}.")
    creator = _event_creators.get(datatype)
    if creator is None:
        raise NotImplementedError(f"{datatype} does not support event creation.")
    return creator(datasource)


def create_seismogram(
    datasource: str | PathLike, datatype: DataType
) -> AimbatSeismogram:
    """Create an `AimbatSeismogram` from a data source.

    Args:
        datasource: Data source path or name.
        datatype: Data type of the source.

    Returns:
        A new `AimbatSeismogram` instance.

    Raises:
        NotImplementedError: If `datatype` has no registered seismogram creator.
    """
    logger.debug(f"Creating AimbatSeismogram from {datasource}.")
    creator = _seismogram_creators.get(datatype)
    if creator is None:
        raise NotImplementedError(f"{datatype} does not support seismogram creation.")
    return creator(datasource)


def read_seismogram_data(
    datasource: str | PathLike, datatype: DataType
) -> npt.NDArray[np.float64]:
    """Read seismogram waveform data from a data source.

    Results are cached in memory by `(datasource, datatype)` key. The cache
    entry is invalidated when `write_seismogram_data` is called for the same
    key, and can be cleared manually with `clear_seismogram_cache`.

    Args:
        datasource: Data source path or name.
        datatype: Data type of the source.

    Returns:
        Seismogram waveform data as a NumPy array.

    Raises:
        NotImplementedError: If `datatype` has no registered data reader.
    """
    logger.debug(f"Reading seismogram data from {datasource}.")
    reader = _seismogram_data_readers.get(datatype)
    if reader is None:
        raise NotImplementedError(
            f"{datatype} does not support reading seismogram data."
        )
    key = (str(datasource), datatype)
    if key not in _cache:
        _cache[key] = reader(datasource)
    return _cache[key]


def write_seismogram_data(
    datasource: str | PathLike,
    datatype: DataType,
    data: npt.NDArray[np.float64],
) -> None:
    """Write seismogram waveform data to a data source.

    Invalidates the cache entry for `(datasource, datatype)` after writing.

    Args:
        datasource: Data source path or name.
        datatype: Data type of the source.
        data: Seismogram waveform data to write.

    Raises:
        NotImplementedError: If `datatype` has no registered data writer.
    """
    logger.debug(f"Writing seismogram data to {datasource}.")
    writer = _seismogram_data_writers.get(datatype)
    if writer is None:
        raise NotImplementedError(
            f"{datatype} does not support writing seismogram data."
        )
    writer(datasource, data)
    _cache.pop((str(datasource), datatype), None)
