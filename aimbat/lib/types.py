"""Custom types used in AIMBAT."""

from datetime import datetime, timedelta
from typing import Literal, get_args, Tuple

SeismogramFileType = Literal["sac"]
"""TypeAlias of filetypes that can be imported into AIMBAT."""

SEISMOGRAM_FILE_TYPES: tuple[SeismogramFileType, ...] = get_args(SeismogramFileType)
"""Tuple containing valid filetypes that can be imported into AIMBAT."""


# Valid AIMBAT seismogram  parameter types and names
SeismogramParameterType = float | datetime | timedelta | str
SeismogramParameterName = Literal["select", "t1", "t2"]
SEISMOGRAM_PARAMETER_NAMES: Tuple[SeismogramParameterName, ...] = get_args(
    SeismogramParameterName
)

# Valid AIMBAT event parameter types and names
EventParameterType = timedelta | bool
EventParameterName = Literal["completed", "window_pre", "window_post"]
EVENT_PARAMETER_NAMES: tuple[EventParameterName, ...] = get_args(EventParameterName)
