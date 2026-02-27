from enum import StrEnum, auto

__all__ = [
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
