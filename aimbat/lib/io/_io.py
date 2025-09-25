from __future__ import annotations
from ._sac import (
    create_station_from_sacfile,
    create_event_from_sacfile,
    create_seismogram_from_sacfile,
    read_seismogram_data_from_sacfile,
    write_seismogram_data_to_sacfile,
)
from aimbat.logger import logger
from enum import StrEnum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aimbat.lib.models import (
        AimbatEvent,
        AimbatSeismogram,
        AimbatStation,
    )
    from os import PathLike
    import numpy as np
    import numpy.typing as npt


class DataType(StrEnum):
    """Valid AIMBAT data types."""

    SAC = auto()


station_creator = {DataType.SAC: create_station_from_sacfile}
event_creator = {DataType.SAC: create_event_from_sacfile}
seismogram_creator = {DataType.SAC: create_seismogram_from_sacfile}
seismogram_data_reader = {DataType.SAC: read_seismogram_data_from_sacfile}
seismogram_data_writer = {DataType.SAC: write_seismogram_data_to_sacfile}


def create_station(datasource: str | PathLike, datatype: DataType) -> AimbatStation:
    """Read station data from a data source and create an AimbatStation.

    Parameters:
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

    Parameters:
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

    Parameters:
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
    filename: str | PathLike, datatype: DataType
) -> npt.NDArray[np.float64]:
    """Read seismogram data from a data source.

    Parameters:
        filename: Name of the seismogram file.
        datatype: AIMBAT compatible filetype.

    Returns:
        Seismogram data.

    Raises:
        NotImplementedError: If the datatype is not supported.
    """

    logger.debug(f"Reading seismogram data from {filename}.")

    data_reader_fn = seismogram_data_reader.get(datatype)
    if data_reader_fn is None:
        raise NotImplementedError(f"I don't know how to read data of type {datatype}.")
    return data_reader_fn(filename)


def write_seismogram_data(
    filename: str | PathLike,
    datatype: DataType,
    data: npt.NDArray[np.float64],
) -> None:
    """Write seismogram data to a data source.

    Parameters:
        filename: Name of the seismogram file.
        datatype: AIMBAT compatible filetype.
        data: Seismogram data

    Raises:
        NotImplementedError: If the datatype is not supported.
    """

    logger.debug(f"Writing seismogram data to {filename}.")

    data_writer_fn = seismogram_data_writer.get(datatype)
    if data_writer_fn is None:
        raise NotImplementedError(
            f"I don't know how to write data to file of type {datatype}"
        )
    data_writer_fn(filename, data)
