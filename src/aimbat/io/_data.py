"""Data types recognised by AIMBAT's I/O dispatch layer.

Defines the `DataType` enum used to route station, event, and seismogram
creation and reading/writing to the data source registered for a given type,
along with the file suffixes associated with each type.
"""

from enum import StrEnum, auto

__all__ = [
    "DATATYPE_SUFFIXES",
    "DataType",
]


class DataType(StrEnum):
    """Valid AIMBAT data types."""

    SAC = auto()
    """SAC (Seismic Analysis Code) waveform file. Provides station, event, and seismogram data."""

    JSON_EVENT = auto()
    """JSON file containing a single seismic event record."""

    JSON_STATION = auto()
    """JSON file containing a single seismic station record."""

    MSEED = auto()
    """miniSEED waveform file. Waveform data only - no station or event data."""


DATATYPE_SUFFIXES: dict[DataType, list[str]] = {
    DataType.SAC: [".sac", ".bhz", ".bhn", ".bhe"],
    DataType.JSON_EVENT: [".json"],
    DataType.JSON_STATION: [".json"],
    DataType.MSEED: [".mseed", ".miniseed", ".ms"],
}
