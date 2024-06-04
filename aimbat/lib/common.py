from datetime import datetime, timedelta
from typing import Literal, Tuple, get_args
from dataclasses import dataclass
import re


# File types that AIMBAT can use as input
AimbatFileType = Literal["sac"]
AIMBAT_FILE_TYPES: Tuple[AimbatFileType, ...] = get_args(AimbatFileType)

# Valid AIMBAT parameter types and names
AimbatParameterType = float | datetime | timedelta | str
AimbatParameterName = Literal["select", "t1", "t2", "window_pre", "window_post"]
AIMBAT_PARAMETER_NAMES: Tuple[AimbatParameterName, ...] = get_args(AimbatParameterName)


class AimbatDataError(Exception):
    pass


# some helpers below


@dataclass
class RegexEqual(str):
    string: str

    def __eq__(self, pattern):  # type: ignore
        match = re.search(pattern, self.string)
        return match is not None
