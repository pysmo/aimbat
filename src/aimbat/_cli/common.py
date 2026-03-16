"""Common parameters and functions for the AIMBAT CLI."""

import uuid
from dataclasses import dataclass
from typing import Annotated, Any, Callable

from cyclopts import Parameter, Token

from aimbat import settings

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
            from sqlmodel import Session

            from aimbat.db import engine
            from aimbat.utils import string_to_uuid

            with Session(engine) as session:
                return string_to_uuid(session, value, model_class)

    return converter


def _event_id_converter(hint: type, tokens: tuple[Token, ...]) -> uuid.UUID:
    """Converter for the global --event parameter with late-bound model import."""
    from aimbat.models import AimbatEvent

    return _make_uuid_converter(AimbatEvent)(hint, tokens)


def id_parameter(model_class: type, help: str = "") -> Parameter:
    """Create a Parameter for a record ID with automatic UUID prefix resolution."""
    return Parameter(
        name="ID",
        help=help or "Full UUID or any unique prefix as shown in the table.",
        converter=_make_uuid_converter(model_class),
    )


def _station_id_converter(hint: type, tokens: tuple[Token, ...]) -> uuid.UUID:
    from aimbat.models import AimbatStation

    return _make_uuid_converter(AimbatStation)(hint, tokens)


def event_parameter(help: str = "") -> Parameter:
    """Create a Parameter for --event with automatic UUID prefix resolution."""
    return Parameter(
        name=["event", "event-id"],
        help=help or "Process a specific event instead of default one (if set). ",
        converter=_event_id_converter,
    )


def seismogram_parameter(help: str = "") -> Parameter:
    """Create a Parameter for --seismogram with automatic UUID prefix resolution."""
    from aimbat.models import AimbatSeismogram

    return Parameter(
        name=["seismogram", "seismogram-id"],
        help=help
        or "ID of seismogram to process. Full UUID or any unique prefix as shown in the table.",
        converter=_make_uuid_converter(AimbatSeismogram),
    )


def use_station_parameter() -> Parameter:
    """Create a Parameter for --use-station with automatic UUID prefix resolution."""
    return Parameter(
        name="use-station",
        help="UUID (or unique prefix) of an existing station to link to instead of"
        " extracting one from each data source.",
        converter=_station_id_converter,
    )


def use_event_parameter() -> Parameter:
    """Create a Parameter for --use-event with automatic UUID prefix resolution."""
    return Parameter(
        name="use-event",
        help="UUID (or unique prefix) of an existing event to link to instead of"
        " extracting one from each data source.",
        converter=_event_id_converter,
    )


#: Shared Parameter for --all (all events) flags.
ALL_EVENTS_PARAMETER = Parameter(
    name="all",
    help="Include records from all events instead of just the default one.",
)

# -----------------------------------------------------------------------
# Common parameters
# -----------------------------------------------------------------------


@dataclass
class _DebugTrait:
    debug: bool = False
    """Enable verbose logging for troubleshooting."""

    # NOTE: only one __post_init__ is allowed per dataclass
    def __post_init__(self) -> None:
        if self.debug:
            settings.log_level = "DEBUG"
            from aimbat.logger import configure_logging

            configure_logging()


@dataclass
class _AllEventsTrait:
    all_events: Annotated[
        bool,
        Parameter(
            name="all",
            help="Include records from all events. Overrides any event selection parameters.",
        ),
    ] = False


@dataclass
class _EventContextTrait:
    event_id: Annotated[
        uuid.UUID | None,
        Parameter(
            name=["event", "event-id"],
            help="Process a specific event instead of default one (if set). "
            "Full UUID or any unique prefix as shown in the table.",
            converter=_event_id_converter,
        ),
    ] = None


@dataclass
class _ByAliasTrait:
    by_alias: Annotated[
        bool,
        Parameter(
            name="alias",
            help="Dump records using their alias instead of attribute names.",
        ),
    ] = False


@Parameter(name="*")
@dataclass
class DebugParameter(_DebugTrait):
    pass


@Parameter(name="*")
@dataclass
class JsonDumpParameters(_ByAliasTrait, _DebugTrait):
    pass


@Parameter(name="*")
@dataclass
class GlobalParameters(_DebugTrait, _AllEventsTrait, _EventContextTrait):
    """Parameters for commands that operate on individual or all events, with optional debug mode."""

    pass


@Parameter(name="*")
@dataclass
class IccsPlotParameters:
    context: bool = True
    "Plot seismograms with extra context instead of the short tapered ones used for cross-correlation."
    all_seismograms: Annotated[bool, Parameter(name="all")] = False
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
    import sys
    from functools import wraps

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
