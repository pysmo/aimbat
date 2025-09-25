"""Functions to read and write data files used with AIMBAT"""

from ._io import (
    DataType,
    create_event,
    create_seismogram,
    create_station,
    read_seismogram_data,
    write_seismogram_data,
)

__all__ = [
    "DataType",
    "create_event",
    "create_seismogram",
    "create_station",
    "read_seismogram_data",
    "write_seismogram_data",
]
