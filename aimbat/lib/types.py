"""Custom types used in AIMBAT."""

from datetime import datetime, timedelta
from typing import Literal, get_args, Tuple

AimbatFileType = Literal["sac"]
"""TypeAlias of filetypes that can be imported into AIMBAT."""

AIMBAT_FILE_TYPES: tuple[AimbatFileType, ...] = get_args(AimbatFileType)
"""Tuple containing valid filetypes that can be imported into AIMBAT."""


# Valid AIMBAT seismogram  parameter types and names
AimbatSeismogramParameterType = float | datetime | timedelta | str
AimbatSeismogramParameterName = Literal["select", "t1", "t2"]
AIMBAT_SEISMOGRAM_PARAMETER_NAMES: Tuple[AimbatSeismogramParameterName, ...] = get_args(
    AimbatSeismogramParameterName
)

# Valid AIMBAT event parameter types and names
AimbatEventParameterType = timedelta | bool
AimbatEventParameterName = Literal["completed", "window_pre", "window_post"]
AIMBAT_EVENT_PARAMETER_NAMES: tuple[AimbatEventParameterName, ...] = get_args(
    AimbatEventParameterName
)

TAimbatDefault = float | int | bool | str
