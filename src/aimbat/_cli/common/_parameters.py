"""Common parameters and functions for the AIMBAT CLI."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal, overload
from uuid import UUID

from cyclopts import Parameter, Token

from aimbat import settings

try:
    from typing import TypeIs
except ImportError:
    from typing_extensions import TypeIs

__all__ = [
    "id_parameter",
    "event_parameter",
    "event_parameter_with_all",
    "event_parameter_is_all",
    "use_station_parameter",
    "use_event_parameter",
    "use_matrix_image",
    "DebugParameter",
    "EventDebugParameters",
    "IccsPlotParameters",
    "TableParameters",
    "JsonDumpParameters",
]


# -----------------------------------------------------------------------
# Shared Parameter instances and factories
# -----------------------------------------------------------------------


@overload
def _make_uuid_converter(
    model_class: type, allow_all: Literal[False] = ...
) -> Callable[..., UUID]: ...


@overload
def _make_uuid_converter(
    model_class: type, allow_all: Literal[True]
) -> Callable[..., UUID | Literal["all"]]: ...


def _make_uuid_converter(
    model_class: type, allow_all: bool = False
) -> Callable[..., UUID | Literal["all"]]:
    """Return a cyclopts converter that resolves a UUID prefix for the given model.

    Args:
     model_class: AIMBAT model class to resolve the UUID against.
     allow_all: If True, the converter will also accept the string "all"
        (case-insensitive) and return it as a literal.
    """

    def _converter(hint: type, tokens: tuple[Token, ...]) -> UUID | Literal["all"]:
        (token,) = tokens
        value = token.value

        if allow_all and value.lower() == "all":
            return "all"
        try:
            return UUID(value)
        except ValueError:
            from sqlmodel import Session

            from aimbat.db import engine
            from aimbat.utils import string_to_uuid

            with Session(engine) as session:
                return string_to_uuid(session, value, model_class)

    return _converter


def id_parameter(model_class: type, help: str = "") -> Parameter:
    return Parameter(
        name="id",
        help=help or "UUID (or any unique prefix).",
        converter=_make_uuid_converter(model_class),
    )


def event_parameter(help: str | None = None) -> Parameter:
    from aimbat.models import AimbatEvent

    return Parameter(
        name=["event", "event-id"],
        help=help or "UUID (or unique prefix) of event to process.",
        env_var="DEFAULT_EVENT_ID",
        converter=_make_uuid_converter(AimbatEvent),
    )


def event_parameter_with_all(help: str | None = None) -> Parameter:
    from aimbat.models import AimbatEvent

    return Parameter(
        name=["event", "event-id"],
        help=help
        or '"all" for all events, or UUID (or unique prefix) of event to process.',
        env_var="DEFAULT_EVENT_ID",
        converter=_make_uuid_converter(AimbatEvent, allow_all=True),
        show_choices=False,
    )


def event_parameter_is_all(event_id: UUID | Literal["all"]) -> TypeIs[Literal["all"]]:
    if isinstance(event_id, str) and event_id.lower() == "all":
        return True
    return False


def use_station_parameter() -> Parameter:
    from aimbat.models import AimbatStation

    return Parameter(
        name="use-station",
        help="UUID (or unique prefix) of an existing station to link to instead of"
        " extracting one from each data source.",
        converter=_make_uuid_converter(AimbatStation),
    )


def use_event_parameter() -> Parameter:
    from aimbat.models import AimbatEvent

    return Parameter(
        name="use-event",
        help="UUID (or unique prefix) of an existing event to link to instead of"
        " extracting one from each data source.",
        converter=_make_uuid_converter(AimbatEvent),
    )


def use_matrix_image() -> Parameter:
    return Parameter(
        name="matrix",
        help="Use matrix image instead of stack plot.",
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
class _EventContextTrait:
    event_id: Annotated[UUID, event_parameter()]


@dataclass
class _TableParametersTrait:
    raw: bool = False


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
class EventDebugParameters(_DebugTrait, _EventContextTrait):
    """Parameters for commands that operate on individual events, with optional debug mode."""

    pass


@Parameter(name="*")
@dataclass
class JsonDumpParameters(_ByAliasTrait, _DebugTrait):
    pass


@Parameter(name="*")
@dataclass
class TableParameters(_TableParametersTrait, _DebugTrait):
    pass


@Parameter(name="*")
@dataclass
class DebugParameter(_DebugTrait):
    pass


@Parameter(name="*")
@dataclass
class IccsPlotParameters:
    context: Annotated[
        bool,
        Parameter(
            help="Plot seismograms with extra context instead of the short tapered ones used for cross-correlation"
        ),
    ] = True
    all_seismograms: Annotated[
        bool,
        Parameter(
            name="all",
            help="Include all seismograms in the plot, even if not used in stack.",
        ),
    ] = False
