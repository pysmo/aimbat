"""Custom types used in AIMBAT."""

from typing import Literal
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
    BANDPASS_APPLY = auto()
    BANDPASS_FMIN = auto()
    BANDPASS_FMAX = auto()


type EventParameterBool = Literal[
    EventParameter.COMPLETED, EventParameter.BANDPASS_APPLY
]
"[`TypeAlias`][typing.TypeAlias] for [`AimbatEvent`][aimbat.lib.models.AimbatEvent] attributes with [`bool`][bool] values."

type EventParameterFloat = Literal[
    EventParameter.MIN_CCNORM,
    EventParameter.BANDPASS_FMIN,
    EventParameter.BANDPASS_FMAX,
]
"[`TypeAlias`][typing.TypeAlias] for [`AimbatEvent`][aimbat.lib.models.AimbatEvent] attributes with [`float`][float] values."

type EventParameterTimedelta = Literal[
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


type SeismogramParameterBool = Literal[
    SeismogramParameter.SELECT, SeismogramParameter.FLIP
]
type SeismogramParameterDatetime = Literal[SeismogramParameter.T1]
