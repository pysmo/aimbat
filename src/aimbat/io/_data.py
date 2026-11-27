"""Data types recognised by AIMBAT's I/O dispatch layer.

Defines the `DataType` enum used to route station, event, and seismogram
creation and reading/writing to the data source registered for a given type,
along with `DATATYPE_SUFFIXES`, which maps each type to its file suffixes.
`DATATYPE_SUFFIXES` applies only to file-based sources (all current types);
non-file sources of a given type are not described by it.
"""

from enum import StrEnum, auto
from pathlib import PurePath

__all__ = [
    "DATATYPE_SUFFIXES",
    "DataType",
    "has_datatype_suffix",
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
    DataType.SAC: [".sac"],
    DataType.JSON_EVENT: [".json"],
    DataType.JSON_STATION: [".json"],
    DataType.MSEED: [".mseed", ".miniseed", ".ms"],
}
"""`.json` maps to both `JSON_EVENT` and `JSON_STATION`, so a suffix alone
never resolves to one `DataType` - callers must pass an explicit `DataType`
for JSON sources rather than inferring it from this mapping. SAC files are
also commonly named by channel code (`.BHZ`), which `has_datatype_suffix`
accepts."""


_SEED_BANDS = frozenset("FGDCESHBMLVURPTQAO")
_SEED_INSTRUMENTS = frozenset("HLGN")
"""Seismometers (high and low gain), gravimeters and accelerometers."""
_SEED_ORIENTATIONS = frozenset("ZNEABCTRQLUVW123")


def has_datatype_suffix(path: PurePath, datatype: DataType) -> bool:
    """Return whether a file name has a suffix usual for a data type.

    For SAC, a SEED channel code of a seismometer, gravimeter or
    accelerometer counts too, since SAC files are commonly named by their
    channel code (`.BHZ`, `.BHT`).

    Args:
        path: Path of the file.
        datatype: The data type.
    """
    suffix = path.suffix.lower()
    if suffix in DATATYPE_SUFFIXES[datatype]:
        return True
    code = suffix.removeprefix(".").upper()
    return (
        datatype is DataType.SAC
        and len(code) == 3
        and code[0] in _SEED_BANDS
        and code[1] in _SEED_INSTRUMENTS
        and code[2] in _SEED_ORIENTATIONS
    )
