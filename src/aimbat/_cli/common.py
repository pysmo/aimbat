"""Common parameters and functions for the AIMBAT CLI."""

from aimbat import settings
from dataclasses import dataclass
from cyclopts import Parameter, Token
from typing import Callable, Any, Annotated
import uuid

# -----------------------------------------------------------------------
# Shared Parameter instances and factories
# -----------------------------------------------------------------------


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


def _event_id_converter(hint: type, tokens: tuple[Token, ...]) -> uuid.UUID:
    """Converter for the global --event parameter with late-bound model import."""
    from aimbat.models import AimbatEvent

    return _make_uuid_converter(AimbatEvent)(hint, tokens)


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


#: Shared Parameter for --all (all events) flags.
ALL_EVENTS_PARAMETER = Parameter(
    name="all",
    help="Include records from all events instead of just the default one.",
)

# -----------------------------------------------------------------------
# Common parameters
# -----------------------------------------------------------------------


@Parameter(name="*")
@dataclass
class DebugTrait:
    debug: bool = False
    """Enable verbose logging for troubleshooting."""

    # NOTE: only one __post_init__ is allowed per dataclass
    def __post_init__(self) -> None:
        if self.debug:
            settings.log_level = "DEBUG"
            from aimbat.logger import configure_logging

            configure_logging()


@Parameter(name="*")
@dataclass
class EventContextTrait:
    event_id: Annotated[
        uuid.UUID | None,
        Parameter(
            name=["event", "event-id"],
            help="Process a specific event instead of the default one. "
            "Full UUID or any unique prefix as shown in the table.",
            converter=_event_id_converter,
        ),
    ] = None


@dataclass
class GlobalParameters(DebugTrait, EventContextTrait):
    pass


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


# -------------------------------------------------
# Decorators
# -------------------------------------------------


def print_error_panel(e: Exception) -> None:
    """Print an exception to the console in a red panel."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console(stderr=True)
    panel = Panel(
        f"{e}",
        title="Error",
        title_align="left",
        border_style="red",
        expand=True,
    )
    console.print(panel)


def simple_exception[F: Callable[..., Any]](func: F) -> F:
    """Decorator to handle exceptions and print them to the console.

    Using this decorator prints only the exception to the console without
    traceback, and then exits. In debugging mode this decorator returns the
    callable unchanged.
    """
    from functools import wraps
    import sys

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if settings.log_level in ("TRACE", "DEBUG"):
            return func(*args, **kwargs)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print_error_panel(e)
            sys.exit(1)

    return wrapper  # type: ignore
