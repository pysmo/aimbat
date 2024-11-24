from dataclasses import dataclass
from typing import TYPE_CHECKING
from icecream import ic  # type: ignore
from typer import Context

if TYPE_CHECKING:
    # from sqlmodel import Session
    from sqlalchemy import Engine

ic.disable()


def debug_callback(ctx: Context) -> None:
    """Enable icecream debugging if cli flag is set."""
    _ = ctx.ensure_object(dict)
    debug: bool = ctx.obj.get("DEBUG", False)
    if debug:
        ic.enable()


def engine_from_url(url: str | None = None) -> "Engine":
    """Create an engine from url or return default engine."""
    from aimbat.lib.db import engine
    from sqlmodel import create_engine

    if url is not None:
        engine = create_engine(url)
    return engine


class AimbatDataError(Exception):
    pass


# NOTE: https://stackoverflow.com/questions/15411967/how-can-i-check-if-code-is-executed-in-the-ipython-notebook
def check_for_notebook() -> bool:
    """Check if we ware running inside a jupyter notebook."""
    from IPython.core.getipython import get_ipython

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
        import re

        match = re.search(pattern, self.string)
        return match is not None
