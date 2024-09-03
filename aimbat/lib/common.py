from typing import Literal, Tuple, get_args
from dataclasses import dataclass
import re


# File types that AIMBAT can use as input
AimbatFileType = Literal["sac"]
AIMBAT_FILE_TYPES: Tuple[AimbatFileType, ...] = get_args(AimbatFileType)


class AimbatDataError(Exception):
    pass


# some helpers below


@dataclass
class RegexEqual(str):
    string: str

    def __eq__(self, pattern):  # type: ignore
        match = re.search(pattern, self.string)
        return match is not None
