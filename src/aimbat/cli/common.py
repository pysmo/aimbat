"""Common parameters and functions for the AIMBAT CLI."""

from aimbat import settings
from dataclasses import dataclass
from cyclopts import Parameter
from typing import Callable, Any

# --------------------------------------------------
# Common parameters
# --------------------------------------------------


@Parameter(name="*")
@dataclass
class GlobalParameters:
    debug: bool = False
    "Run in debugging mode."

    use_qt: bool = False
    "Use pyqtgraph instead of matplotlib for plots (where applicable)."

    def __post_init__(self) -> None:
        if self.debug:
            settings.log_level = "DEBUG"


@Parameter(name="*")
@dataclass
class TableParameters:
    short: bool = True
    "Shorten UUIDs and format data."


# ------------------------------------------------
# Hints for error messages
# ------------------------------------------------


@dataclass(frozen=True)
class CliHints:
    """Hints for error messages."""

    ACTIVATE_EVENT = "Hint: activate an event with `aimbat event activate <EVENT_ID>`."
    LIST_EVENTS = "Hint: view available events with `aimbat event list`."


HINTS = CliHints()


# -------------------------------------------------
# Decorators
# -------------------------------------------------


def simple_exception[F: Callable[..., Any]](func: F) -> F:
    """Decorator to handle exceptions and print them to the console.

    Using this decorator prints only the exception to the console without
    traceback, and then exits. In debugging mode this decorator returns the
    callable unchanged.
    """
    from functools import wraps
    from rich.console import Console
    from rich.panel import Panel
    import sys

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if settings.log_level in ("TRACE", "DEBUG"):
            return func(*args, **kwargs)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            console = Console()
            panel = Panel(
                f"{e}",
                title="Error",
                title_align="left",
                border_style="red",
                expand=True,
            )
            console.print(panel)
            sys.exit(1)

    return wrapper  # type: ignore
