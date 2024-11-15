from typing import Literal, get_args
from dataclasses import dataclass
from icecream import ic  # type: ignore
import re
import click


# File types that AIMBAT can use as input
AimbatFileType = Literal["sac"]
AIMBAT_FILE_TYPES: tuple[AimbatFileType, ...] = get_args(AimbatFileType)


class AimbatDataError(Exception):
    pass


# some helpers below
def cli_enable_debug(ctx: click.Context) -> None:
    """Enable icecream debugging if cli flag is set."""
    _ = ctx.ensure_object(dict)
    debug: bool = ctx.obj.get("DEBUG", False)
    if debug:
        ic.enable()


@dataclass
class RegexEqual(str):
    string: str

    def __eq__(self, pattern):  # type: ignore
        match = re.search(pattern, self.string)
        return match is not None
