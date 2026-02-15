"""Custom types used in AIMBAT."""

from typing import Literal, TypeAlias
from enum import StrEnum, auto


class EventParameter(StrEnum):
    """[`AimbatEvent`][aimbat.lib.models.AimbatEvent] enum class for typing.

    This enum class is used for typing, cli args etc. The attributes must be
    the same as in the [`AimbatEvent`][aimbat.lib.models.AimbatEvent] model.
    """

    COMPLETED = auto()
    MIN_CCNORM = auto()
    WINDOW_PRE = auto()
    WINDOW_POST = auto()


EventParameterBool: TypeAlias = Literal[EventParameter.COMPLETED]
"[`TypeAlias`][typing.TypeAlias] for [`AimbatEvent`][aimbat.lib.models.AimbatEvent] attributes with [`bool`][bool] values."

EventParameterFloat: TypeAlias = Literal[EventParameter.MIN_CCNORM]
"[`TypeAlias`][typing.TypeAlias] for [`AimbatEvent`][aimbat.lib.models.AimbatEvent] attributes with [`float`][float] values."

EventParameterTimedelta: TypeAlias = Literal[
    EventParameter.WINDOW_PRE, EventParameter.WINDOW_POST
]
"[`TypeAlias`][typing.TypeAlias] for [`AimbatEvent`][aimbat.lib.models.AimbatEvent] attributes with [`timedelta`][datetime.timedelta] values."


class SeismogramParameter(StrEnum):
    """[`AimbatSeismograParameters`][aimbat.lib.models.AimbatSeismogramParameters] enum class for typing.

    This enum class is used for typing, cli args etc. The attributes must be
    the same as in the [`AimbatParameters`][aimbat.lib.models.AimbatParameters] model.
    """

    SELECT = auto()
    FLIP = auto()
    T1 = auto()


SeismogramParameterBool: TypeAlias = Literal[
    SeismogramParameter.SELECT, SeismogramParameter.FLIP
]
SeismogramParameterDatetime: TypeAlias = Literal[SeismogramParameter.T1]
