"""Custom types used in AIMBAT."""

from typing import Literal
from enum import StrEnum


class SeismogramFileType(StrEnum):
    SAC = "sac"


class AimbatFileAttribute(StrEnum):
    FILENAME = "filename"
    FILETYPE = "filetype"


# ***
# AimbatDefault related types
# ***
class ProjectDefault(StrEnum):
    AIMBAT = "aimbat"
    SAMPLEDATA_DIR = "sampledata_dir"
    SAMPLEDATA_SRC = "sampledata_src"
    DELTA_TOLERANCE = "delta_tolerance"
    INITIAL_PICK_HEADER = "initial_pick_header"
    INITIAL_TIME_WINDOW_WIDTH = "initial_time_window_width"


TDefaultBool = Literal[ProjectDefault.AIMBAT]
TDefaultStr = Literal[
    ProjectDefault.INITIAL_PICK_HEADER,
    ProjectDefault.SAMPLEDATA_SRC,
    ProjectDefault.SAMPLEDATA_DIR,
]
TDefaultInt = Literal[ProjectDefault.DELTA_TOLERANCE]
TDefaultFloat = Literal[ProjectDefault.INITIAL_TIME_WINDOW_WIDTH]


# ***
# AimbatEventParameters related types
# ***
class EventParameter(StrEnum):
    COMPLETED = "completed"
    WINDOW_PRE = "window_pre"
    WINDOW_POST = "window_post"


TEventParameterBool = Literal[EventParameter.COMPLETED]
TEventParameterTimedelta = Literal[
    EventParameter.WINDOW_PRE, EventParameter.WINDOW_POST
]


# ***
# AimbatSeismogramParameters related types
# ***
class SeismogramParameter(StrEnum):
    SELECT = "select"
    T1 = "t1"
    T2 = "t2"


TSeismogramParameterBool = Literal[SeismogramParameter.SELECT]
TSeismogramParameterDatetime = Literal[SeismogramParameter.T1, SeismogramParameter.T2]
