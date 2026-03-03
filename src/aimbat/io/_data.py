from enum import StrEnum, auto

__all__ = [
    "DataType",
    "DATATYPE_SUFFIXES",
]


class DataType(StrEnum):
    """Valid AIMBAT data types."""

    SAC = auto()
    """SAC (Seismic Analysis Code) waveform file. Provides station, event, and seismogram data."""

    JSON_EVENT = auto()
    """JSON file containing a single seismic event record."""

    JSON_STATION = auto()
    """JSON file containing a single seismic station record."""


DATATYPE_SUFFIXES: dict[DataType, list[str]] = {
    DataType.SAC: [".sac", ".bhz", ".bhn", ".bhe"],
    DataType.JSON_EVENT: [".json"],
    DataType.JSON_STATION: [".json"],
}
