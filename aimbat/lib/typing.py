"""Custom types used in AIMBAT."""

from typing import Literal, TypeAlias
from enum import StrEnum, auto


class SeismogramFileType(StrEnum):
    """Valid AIMBAT file types."""

    SAC = auto()


class ProjectDefault(StrEnum):
    """[`AimbatDefaults`][aimbat.lib.models.AimbatDefaults] enum class for typing.

    This enum class is used for typing, cli args etc. The attributes must be
    the same as in the [`AimbatDefaults`][aimbat.lib.models.AimbatDefaults] model.
    """

    AIMBAT = auto()
    SAMPLEDATA_DIR = auto()
    SAMPLEDATA_SRC = auto()
    DELTA_TOLERANCE = auto()
    INITIAL_PICK_HEADER = auto()
    INITIAL_TIME_WINDOW_WIDTH = auto()
    TIME_WINDOW_PADDING = auto()


ProjectDefaultBool: TypeAlias = Literal[ProjectDefault.AIMBAT]
"""[`TypeAlias`][typing.TypeAlias] for [`AimbatDefaults`][aimbat.lib.models.AimbatDefaults]
attributes with [`bool`][bool] values."""

ProjectDefaultStr: TypeAlias = Literal[
    ProjectDefault.INITIAL_PICK_HEADER,
    ProjectDefault.SAMPLEDATA_SRC,
    ProjectDefault.SAMPLEDATA_DIR,
]
"""[`TypeAlias`][typing.TypeAlias] for [`AimbatDefaults`][aimbat.lib.models.AimbatDefaults]
attributes with [`str`][str] values."""

ProjectDefaultInt: TypeAlias = Literal[ProjectDefault.DELTA_TOLERANCE]
"[`TypeAlias`][typing.TypeAlias] for [`AimbatDefaults`][aimbat.lib.models.AimbatDefaults] attributes with [`int`][int] values."

# ProjectDefaultFloat: TypeAlias = Literal[ProjectDefault.TIME_WINDOW_PADDING]
# "[`TypeAlias`][typing.TypeAlias] for [`AimbatDefaults`][aimbat.lib.models.AimbatDefaults] attributes with [`float`][float] values."

ProjectDefaultTimedelta: TypeAlias = Literal[
    ProjectDefault.INITIAL_TIME_WINDOW_WIDTH, ProjectDefault.TIME_WINDOW_PADDING
]
"[`TypeAlias`][typing.TypeAlias] for [`AimbatDefaults`][aimbat.lib.models.AimbatDefaults] attributes with [`timedelta`][timedelta] values."


class EventParameter(StrEnum):
    """[`AimbatEvent`][aimbat.lib.models.AimbatEvent] enum class for typing.

    This enum class is used for typing, cli args etc. The attributes must be
    the same as in the [`AimbatEvent`][aimbat.lib.models.AimbatEvent] model.
    """

    COMPLETED = auto()
    WINDOW_PRE = auto()
    WINDOW_POST = auto()


EventParameterBool: TypeAlias = Literal[EventParameter.COMPLETED]
"[`TypeAlias`][typing.TypeAlias] for [`AimbatEvent`][aimbat.lib.models.AimbatEvent] attributes with [`bool`][bool] values."
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
