from __future__ import annotations
from . import _sac as sac
from aimbat.aimbat_types import DataType
from aimbat.logger import logger
from os import PathLike
from typing import TYPE_CHECKING
import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from aimbat.models import (
        AimbatEvent,
        AimbatSeismogram,
        AimbatStation,
    )


__all__ = [
    "create_event",
    "create_seismogram",
    "create_station",
    "read_seismogram_data",
    "write_seismogram_data",
]


station_creator = {DataType.SAC: sac.create_station_from_sacfile}
event_creator = {DataType.SAC: sac.create_event_from_sacfile}
seismogram_creator = {DataType.SAC: sac.create_seismogram_from_sacfile}
seismogram_data_reader = {DataType.SAC: sac.read_seismogram_data_from_sacfile}
seismogram_data_writer = {DataType.SAC: sac.write_seismogram_data_to_sacfile}


def create_station(datasource: str | PathLike, datatype: DataType) -> AimbatStation:
    """Read station data from a data source and create an AimbatStation.

    Args:
        datasource: Name of the data source.
        datatype: AIMBAT compatible datatype.

    Returns:
        AimbatStation instance.

    Raises:
        NotImplementedError: If the datatype is not supported.
    """

    logger.debug(f"Creating AimbatStation from {datasource}.")

    station_creator_fn = station_creator.get(datatype)
    if station_creator_fn is None:
        raise NotImplementedError(
            f"I don't know how to create an AimbatStation from {datatype}."
        )
    return station_creator_fn(datasource)


def create_event(datasource: str | PathLike, datatype: DataType) -> AimbatEvent:
    """Read event data from a data source and create an AimbatEvent.

    Args:
        datasource: Name of the data source.
        datatype: AIMBAT compatible datatype.

    Returns:
        AimbatEvent instance.

    Raises:
        NotImplementedError: If the datatype is not supported.
    """

    logger.debug(f"Creating AimbatEvent from {datasource}.")

    event_creator_fn = event_creator.get(datatype)
    if event_creator_fn is None:
        raise NotImplementedError(
            f"I don't know how to create an AimbatEvent from {datatype}."
        )
    return event_creator_fn(datasource)


def create_seismogram(
    datasource: str | PathLike, datatype: DataType
) -> AimbatSeismogram:
    """Read seismogram data from a data source and create an AimbatSeismogram.

    Args:
        datasource: Name of the data source.
        datatype: AIMBAT compatible datatype.

    Returns:
        AimbatSeismogram instance.

    Raises:
        NotImplementedError: If the datatype is not supported.
    """

    logger.debug(f"Creating AimbatSeismogram from {datasource}.")

    station_creator_fn = seismogram_creator.get(datatype)
    if station_creator_fn is None:
        raise NotImplementedError(
            f"I don't know how to create an AimbatSeismgoram from {datatype}."
        )
    return station_creator_fn(datasource)


def read_seismogram_data(
    datasource: str | PathLike, datatype: DataType
) -> npt.NDArray[np.float64]:
    """Read seismogram data from a data source.

    Args:
        datasource: Name of the data source.
        datatype: AIMBAT compatible filetype.

    Returns:
        Seismogram data.

    Raises:
        NotImplementedError: If the datatype is not supported.
    """

    logger.debug(f"Reading seismogram data from {datasource}.")

    data_reader_fn = seismogram_data_reader.get(datatype)
    if data_reader_fn is None:
        raise NotImplementedError(f"I don't know how to read data of type {datatype}.")
    return data_reader_fn(datasource)


def write_seismogram_data(
    datasource: str | PathLike,
    datatype: DataType,
    data: npt.NDArray[np.float64],
) -> None:
    """Write seismogram data to a data source.

    Args:
        datasource: Name of the data source.
        datatype: AIMBAT compatible filetype.
        data: Seismogram data

    Raises:
        NotImplementedError: If the datatype is not supported.
    """

    logger.debug(f"Writing seismogram data to {datasource}.")

    data_writer_fn = seismogram_data_writer.get(datatype)
    if data_writer_fn is None:
        raise NotImplementedError(
            f"I don't know how to write data to file of type {datatype}"
        )
    data_writer_fn(datasource, data)
