from typing import Literal, Tuple, get_args


class AimbatDataError(Exception):
    pass


# File types that AIMBAT can use as input
AimbatFileType = Literal["sac"]
AIMBAT_FILE_TYPES: Tuple[AimbatFileType, ...] = get_args(AimbatFileType)
