"""Common parameters and functions for the AIMBAT CLI."""

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal, overload
from uuid import UUID

from cyclopts import Parameter, Token

from aimbat import settings

if sys.version_info >= (3, 13):
    from typing import TypeIs
else:
    from typing_extensions import TypeIs

__all__ = [
    "id_parameter",
    "event_parameter",
    "event_parameter_with_all",
    "event_parameter_is_all",
    "station_parameter_with_all",
    "station_parameter_is_all",
    "use_station_parameter",
    "use_event_parameter",
    "use_matrix_image",
    "open_in_editor",
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
    """Return a cyclopts `Parameter` for selecting a record by UUID or unique prefix.

    Args:
        model_class: AIMBAT model class used to resolve short UUID prefixes.
        help: Custom help string; falls back to a generic UUID prompt if empty.
    """
    return Parameter(
        name="id",
        help=help or "UUID (or any unique prefix).",
        converter=_make_uuid_converter(model_class),
    )


def event_parameter(help: str | None = None) -> Parameter:
    """Return a cyclopts `Parameter` for selecting a single event by UUID or prefix.

    Args:
        help: Custom help string; falls back to a generic event UUID prompt.
    """
    from aimbat.models import AimbatEvent

    return Parameter(
        name=["event", "event-id"],
        help=help or "UUID (or unique prefix) of event to process.",
        env_var="DEFAULT_EVENT_ID",
        converter=_make_uuid_converter(AimbatEvent),
    )


def event_parameter_with_all(help: str | None = None) -> Parameter:
    """Return a cyclopts `Parameter` for selecting an event or the literal `"all"`.

    Args:
        help: Custom help string; falls back to a generic prompt.
    """
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
    """Return `True` if `event_id` is the literal string `"all"` (case-insensitive)."""
    if isinstance(event_id, str) and event_id.lower() == "all":
        return True
    return False


def station_parameter_with_all(help: str | None = None) -> Parameter:
    """Return a cyclopts `Parameter` for selecting a station or the literal `"all"`.

    Args:
        help: Custom help string; falls back to a generic prompt.
    """
    from aimbat.models import AimbatStation

    return Parameter(
        name=["station", "station-id"],
        help=help
        or '"all" for all stations, or UUID (or unique prefix) of station to process.',
        converter=_make_uuid_converter(AimbatStation, allow_all=True),
        show_choices=False,
    )


def station_parameter_is_all(
    station_id: UUID | Literal["all"],
) -> TypeIs[Literal["all"]]:
    """Return `True` if `station_id` is the literal string `"all"` (case-insensitive)."""
    if isinstance(station_id, str) and station_id.lower() == "all":
        return True
    return False


def use_station_parameter() -> Parameter:
    """Return a cyclopts `Parameter` for linking data to an existing station record."""
    from aimbat.models import AimbatStation

    return Parameter(
        name="use-station",
        help="UUID (or unique prefix) of an existing station to link to instead of"
        " extracting one from each data source.",
        converter=_make_uuid_converter(AimbatStation),
    )


def use_event_parameter() -> Parameter:
    """Return a cyclopts `Parameter` for linking data to an existing event record."""
    from aimbat.models import AimbatEvent

    return Parameter(
        name="use-event",
        help="UUID (or unique prefix) of an existing event to link to instead of"
        " extracting one from each data source.",
        converter=_make_uuid_converter(AimbatEvent),
    )


def use_matrix_image() -> Parameter:
    """Return a cyclopts `Parameter` for switching from stack to matrix image plots."""
    return Parameter(
        name="matrix",
        help="Use matrix image instead of stack plot.",
    )


# -----------------------------------------------------------------------
# Editor helper
# -----------------------------------------------------------------------


def open_in_editor(initial_content: str) -> str:
    """Write `initial_content` to a temporary Markdown file, open it in `$EDITOR`,
    and return the (possibly updated) content after the editor exits.

    The temporary file uses `delete=False` so that it can be opened by a
    second process on Windows (which prohibits opening a file that is already
    open). It is always removed in a `finally` block.

    The editor command is taken from `$EDITOR` or `$VISUAL`. If neither is
    set, `notepad` is used on Windows and `vi` elsewhere. To use a GUI editor
    that does not block by default (e.g. VS Code), set
    ``EDITOR="code --wait"``.
    """
    import os
    import shlex
    import subprocess
    import tempfile

    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        editor = "notepad" if sys.platform == "win32" else "vi"

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(initial_content)
        tmp_path = tmp.name

    try:
        result = subprocess.run([*shlex.split(editor), tmp_path], check=False)
        if result.returncode != 0:
            from aimbat.logger import logger

            logger.warning(
                f"Editor '{editor}' exited with code {result.returncode}; discarding changes."
            )
            return initial_content
        with open(tmp_path, encoding="utf-8") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)


# -----------------------------------------------------------------------
# Common parameters
# -----------------------------------------------------------------------


@dataclass
class _DebugTrait:
    """Mixin that adds an optional `--debug` flag to a CLI command."""

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
    """Mixin that adds a required `--event` argument to a CLI command."""

    event_id: Annotated[UUID, event_parameter()]


@dataclass
class _TableParametersTrait:
    """Mixin that adds a `--raw` flag for unformatted table output."""

    raw: bool = False


@dataclass
class _ByAliasTrait:
    """Mixin that adds a `--alias` flag for alias-keyed JSON output."""

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
    """Shared parameters for JSON dump commands (`--alias`, `--debug`)."""

    pass


@Parameter(name="*")
@dataclass
class TableParameters(_TableParametersTrait, _DebugTrait):
    """Shared parameters for table display commands (`--raw`, `--debug`)."""

    pass


@Parameter(name="*")
@dataclass
class DebugParameter(_DebugTrait):
    """Shared parameter that adds `--debug` to any CLI command."""

    pass


@Parameter(name="*")
@dataclass
class IccsPlotParameters:
    """Shared parameters for ICCS plot commands (`--context`, `--all`)."""

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
