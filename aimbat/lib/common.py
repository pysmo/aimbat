"""Common functions for AIMBAT."""

from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from sqlalchemy import Engine

AIMBAT_LOGFILE = "aimbat.log"

__all__ = ["engine_from_url", "check_for_notebook", "logger"]

logger.remove(0)
_ = logger.add(AIMBAT_LOGFILE, rotation="100 MB", level="INFO")


def engine_from_url(url: str | None = None) -> "Engine":
    """Create an engine from url or return default engine.

    url: Optional database url to create an engine from.
    """
    from aimbat.lib.db import engine
    from sqlmodel import create_engine

    if url is not None:
        logger.debug(f"Creating database engine from {url}")
        engine = create_engine(url)
    else:
        logger.debug("No database url provided, using default engine.")

    return engine


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
