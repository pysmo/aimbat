from datetime import datetime, timedelta
from typing import Literal, get_args, Tuple

#
# File types that AIMBAT can use as input
AimbatFileType = Literal["sac"]
AIMBAT_FILE_TYPES: tuple[AimbatFileType, ...] = get_args(AimbatFileType)


# Valid AIMBAT seismogram  parameter types and names
AimbatSeismogramParameterType = float | datetime | timedelta | str
AimbatSeismogramParameterName = Literal["select", "t1", "t2"]
AIMBAT_SEISMOGRAM_PARAMETER_NAMES: Tuple[AimbatSeismogramParameterName, ...] = get_args(
    AimbatSeismogramParameterName
)

# Valid AIMBAT event parameter types and names
AimbatEventParameterType = timedelta
AimbatEventParameterName = Literal["window_pre", "window_post"]
AIMBAT_EVENT_PARAMETER_NAMES: tuple[AimbatEventParameterName, ...] = get_args(
    AimbatEventParameterName
)
