from enum import StrEnum, auto

__all__ = [
    "DataType",
]


class DataType(StrEnum):
    """Valid AIMBAT data types."""

    SAC = auto()
