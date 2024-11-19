from typing import Literal, get_args
from dataclasses import dataclass
from icecream import ic  # type: ignore
from IPython.core.getipython import get_ipython
import re
import click


# File types that AIMBAT can use as input
AimbatFileType = Literal["sac"]
AIMBAT_FILE_TYPES: tuple[AimbatFileType, ...] = get_args(AimbatFileType)


class AimbatDataError(Exception):
    pass


def cli_enable_debug(ctx: click.Context) -> None:
    """Enable icecream debugging if cli flag is set."""
    _ = ctx.ensure_object(dict)
    debug: bool = ctx.obj.get("DEBUG", False)
    if debug:
        ic.enable()


# NOTE: https://stackoverflow.com/questions/15411967/how-can-i-check-if-code-is-executed-in-the-ipython-notebook
def check_for_notebook() -> bool:
    """Check if we ware running inside a jupyter notebook."""
    try:
        shell = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False  # Probably standard Python interpreter


@dataclass
class RegexEqual(str):
    string: str

    def __eq__(self, pattern):  # type: ignore
        match = re.search(pattern, self.string)
        return match is not None
