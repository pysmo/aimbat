"""Common parameters and functions for the AIMBAT CLI."""

from aimbat import settings
from dataclasses import dataclass
from cyclopts import Parameter, Token
from typing import Callable, Any
import uuid

# -----------------------------------------------------------------------
# Common parameters
# -----------------------------------------------------------------------


@Parameter(name="*")
@dataclass
class GlobalParameters:
    debug: bool = False
    "Run in debugging mode."

    def __post_init__(self) -> None:
        if self.debug:
            settings.log_level = "DEBUG"


@Parameter(name="*")
@dataclass
class PlotParameters:
    use_qt: bool = False
    "Use pyqtgraph instead of matplotlib for plots (where applicable)."


@Parameter(name="*")
@dataclass
class IccsPlotParameters:
    context: bool = True
    "Plot seismograms with extra context instead of the short tapered ones used for cross-correlation."
    all: bool = False
    "Include all seismograms in the plot, even if not used in stack."


@Parameter(name="*")
@dataclass
class TableParameters:
    short: bool = True
    "Shorten UUIDs and format data."


# -----------------------------------------------------------------------
# Shared Parameter instances and factories
# -----------------------------------------------------------------------

#: Shared Parameter for --all (all events) flags.
ALL_EVENTS_PARAMETER = Parameter(
    name="all",
    help="Include records from all events instead of just the active one.",
)


def _make_uuid_converter(model_class: type) -> Callable[..., uuid.UUID]:
    """Return a cyclopts converter that resolves a UUID prefix for the given model."""

    def converter(hint: type, tokens: tuple[Token, ...]) -> uuid.UUID:
        (token,) = tokens
        value = token.value
        try:
            return uuid.UUID(value)
        except ValueError:
            from aimbat.db import engine
            from aimbat.utils import string_to_uuid
            from sqlmodel import Session

            with Session(engine) as session:
                return string_to_uuid(session, value, model_class)

    return converter


def id_parameter(model_class: type) -> Parameter:
    """Create a Parameter for a record ID with automatic UUID prefix resolution."""
    return Parameter(
        name="id",
        help="Full UUID or any unique prefix as shown in the table.",
        converter=_make_uuid_converter(model_class),
    )


def use_station_parameter(model_class: type) -> Parameter:
    """Create a Parameter for --use-station with automatic UUID prefix resolution."""
    return Parameter(
        name="use-station",
        help="UUID (or unique prefix) of an existing station to link to instead of"
        " extracting one from each data source.",
        converter=_make_uuid_converter(model_class),
    )


def use_event_parameter(model_class: type) -> Parameter:
    """Create a Parameter for --use-event with automatic UUID prefix resolution."""
    return Parameter(
        name="use-event",
        help="UUID (or unique prefix) of an existing event to link to instead of"
        " extracting one from each data source.",
        converter=_make_uuid_converter(model_class),
    )


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
