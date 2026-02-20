from typing import Literal
from enum import StrEnum, auto

__all__ = [
    "SeismogramParameter",
    "SeismogramParameterBool",
    "SeismogramParameterTimestamp",
]


class SeismogramParameter(StrEnum):
    """[`AimbatSeismograParameters`][aimbat.lib.models.AimbatSeismogramParameters] enum class for typing.

    This enum class is used for typing, cli args etc. The attributes must be
    the same as in the [`AimbatParameters`][aimbat.lib.models.AimbatParameters] model.
    """

    SELECT = auto()
    FLIP = auto()
    T1 = auto()


type SeismogramParameterBool = Literal[
    SeismogramParameter.SELECT, SeismogramParameter.FLIP
]
type SeismogramParameterTimestamp = Literal[SeismogramParameter.T1]
