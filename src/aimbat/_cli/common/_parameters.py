"""Common parameters and functions for the AIMBAT CLI."""

import os
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Literal, TypeIs, get_origin
from uuid import UUID

from cyclopts import Parameter, Token

from aimbat import settings

from ._decorators import print_warning

if TYPE_CHECKING:
    from aimbat.models import AimbatTypes

__all__ = [
    "CAUSAL_DEFAULTS",
    "ComponentConverter",
    "ConfirmParameters",
    "DebugParameter",
    "EventDebugParameters",
    "IccsPlotParameters",
    "JsonDumpParameters",
    "PhaseDebugParameters",
    "PhaseNameConverter",
    "TableParameters",
    "UuidConverter",
    "causal",
    "component_parameter",
    "default_component",
    "event_parameter",
    "event_parameter_is_all",
    "event_parameter_with_all",
    "id_parameter",
    "open_in_editor",
    "phase_filter_parameter",
    "phase_parameter",
    "resolve_phase_option",
    "resolve_seismogram_phase",
    "station_parameter_is_all",
    "station_parameter_with_all",
    "use_event_parameter",
    "use_matrix_image",
    "use_station_parameter",
]


# -----------------------------------------------------------------------
# Shared Parameter instances and factories
# -----------------------------------------------------------------------


@dataclass(frozen=True)
class UuidConverter:
    """Cyclopts converter that resolves a UUID or unique prefix for a model.

    For a list parameter, each token is resolved. `aimbat shell` reads
    `model_class` and `allow_all` to complete IDs.

    Attributes:
        model_class: AIMBAT model class to resolve the UUID against.
        allow_all: Whether the string "all" (case-insensitive) is also accepted
            and returned as a literal.
    """

    model_class: "type[AimbatTypes]"
    allow_all: bool = False

    def __call__(
        self, hint: type, tokens: tuple[Token, ...]
    ) -> UUID | Literal["all"] | list[UUID | Literal["all"]]:
        if get_origin(hint) is list:
            return [self._resolve(token.value) for token in tokens]
        (token,) = tokens
        return self._resolve(token.value)

    def _resolve(self, value: str) -> UUID | Literal["all"]:
        if self.allow_all and value.lower() == "all":
            return "all"
        try:
            return UUID(value)
        except ValueError:
            from sqlmodel import Session

            from aimbat.db import engine
            from aimbat.utils import string_to_uuid

            from ._decorators import run_reporting_issues

            def _resolve() -> UUID:
                with Session(engine) as session:
                    return string_to_uuid(session, value, self.model_class)

            return run_reporting_issues(_resolve)


def id_parameter(model_class: "type[AimbatTypes]", help: str = "") -> Parameter:
    """Return a cyclopts `Parameter` for selecting a record by UUID or unique prefix.

    Args:
        model_class: AIMBAT model class used to resolve short UUID prefixes.
        help: Custom help string; falls back to a generic UUID prompt if empty.
    """
    return Parameter(
        name="id",
        help=help or "UUID (or any unique prefix).",
        converter=UuidConverter(model_class),
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
        converter=UuidConverter(AimbatEvent),
    )


@dataclass(frozen=True)
class PhaseNameConverter:
    """Cyclopts converter that passes a phase name through unchanged.

    The name is resolved against an event by `resolve_phase_option`.
    `aimbat shell` recognises this converter to complete phase names.
    """

    def __call__(self, hint: type, tokens: tuple[Token, ...]) -> str:
        (token,) = tokens
        return token.value


def phase_parameter(help: str | None = None) -> Parameter:
    """Return a cyclopts `Parameter` for selecting a phase by name.

    Args:
        help: Custom help string; falls back to a generic prompt.
    """
    return Parameter(
        name="phase",
        help=help
        or (
            "Name of the phase to process. Not needed when the event has only one"
            + " phase."
        ),
        env_var="DEFAULT_PHASE",
        converter=PhaseNameConverter(),
    )


@dataclass(frozen=True)
class ComponentConverter:
    """Cyclopts converter that upper-cases a component letter.

    `aimbat shell` recognises this converter to complete components.
    """

    def __call__(self, hint: type, tokens: tuple[Token, ...]) -> str:
        (token,) = tokens
        return token.value.strip().upper()


def component_parameter(help: str | None = None) -> Parameter:
    """Return a cyclopts `Parameter` for selecting a phase by component.

    `DEFAULT_COMPONENT` is applied by `default_component`, not by cyclopts,
    so that it only accompanies the phase name it was set with.

    Args:
        help: Custom help string; falls back to a generic prompt.
    """
    return Parameter(
        name="component",
        help=help
        or (
            "Component of the phase to process (Z, T, Q, ...). Not needed when"
            + " the phase name has only one component. Defaults to"
            + " `DEFAULT_COMPONENT` when no phase name or `DEFAULT_PHASE` is"
            + " given."
        ),
        converter=ComponentConverter(),
    )


def default_component(name: str | None, component: str | None) -> str | None:
    """Return the component given, else `DEFAULT_COMPONENT` where it applies.

    `DEFAULT_COMPONENT` applies without a phase name, or with the name in
    `DEFAULT_PHASE`. A different name given with `--phase` does not take
    the component of another phase.
    """
    if component is not None:
        return component
    value = os.environ.get("DEFAULT_COMPONENT")
    if value is None:
        return None
    if name is not None and name != os.environ.get("DEFAULT_PHASE"):
        return None
    return value.strip().upper()


def phase_filter_parameter() -> Parameter:
    """Return a cyclopts `Parameter` for listing only the phases of one name.

    It does not read `DEFAULT_PHASE`, which would leave no way to list every
    phase while the variable is set.
    """
    return Parameter(
        name="phase",
        help="Only show phases of this name.",
        converter=PhaseNameConverter(),
    )


def resolve_phase_option(
    event_id: UUID, name: str | None = None, component: str | None = None
) -> UUID:
    """Return the ID of the phase of an event selected by name and component.

    Raises:
        NoResultFound: If the event does not exist, or no phase of it
            matches.
        AmbiguousPhaseError: If several phases of the event match.
    """
    from sqlmodel import Session

    from aimbat.core import resolve_phase
    from aimbat.db import engine

    component = default_component(name, component)
    with Session(engine) as session:
        return resolve_phase(session, event_id, name, component).id


def resolve_seismogram_phase(seismogram_id: UUID, name: str | None = None) -> UUID:
    """Return the ID of the phase of a seismogram's event on its component.

    Without a name, the only phase of the event on the seismogram's
    component.

    Raises:
        NoResultFound: If the seismogram does not exist, or its event has no
            matching phase on its component.
        AmbiguousPhaseError: If no name is given and the event has several
            phases on the seismogram's component.
    """
    from sqlalchemy.exc import NoResultFound
    from sqlmodel import Session

    from aimbat.core import resolve_phase
    from aimbat.db import engine
    from aimbat.models import AimbatSeismogram, phase_component

    with Session(engine) as session:
        seismogram = session.get(AimbatSeismogram, seismogram_id)
        if seismogram is None:
            raise NoResultFound(f"No seismogram found with ID {seismogram_id}.")
        return resolve_phase(
            session, seismogram.event_id, name, phase_component(seismogram.station)
        ).id


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
        converter=UuidConverter(AimbatEvent, allow_all=True),
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
        converter=UuidConverter(AimbatStation, allow_all=True),
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
        help=(
            "UUID (or unique prefix) of an existing station to link to instead of"
            + " extracting one from each data source."
        ),
        converter=UuidConverter(AimbatStation),
    )


def use_event_parameter() -> Parameter:
    """Return a cyclopts `Parameter` for linking data to an existing event record."""
    from aimbat.models import AimbatEvent

    return Parameter(
        name="use-event",
        help=(
            "UUID (or unique prefix) of an existing event to link to instead of "
            + "extracting one from each data source."
        ),
        converter=UuidConverter(AimbatEvent),
    )


def use_matrix_image() -> Parameter:
    """Return a cyclopts `Parameter` for switching from stack to matrix image plots."""
    return Parameter(
        name="matrix",
        help="Use matrix image instead of stack plot.",
    )


def causal() -> Parameter:
    """Return a cyclopts `Parameter` for switching between causal and zero-phase filtering."""
    return Parameter(
        name="causal",
        help="Use causal (single-pass) instead of zero-phase filtering.",
        negative="--zero-phase",
    )


CAUSAL_DEFAULTS: dict[str, bool] = {
    "pick": True,
    "window": False,
    "cc": False,
}
"""Default causal/zero-phase setting per `tool` subcommand and TUI tool id.

Single source of truth for the `causal()` parameter defaults in
`_cli/tool.py` and the equivalent per-tool defaults in the TUI's
`InteractiveToolsModal` (`_tui/modals.py`).
"""


# -----------------------------------------------------------------------
# Editor helper
# -----------------------------------------------------------------------


def open_in_editor(initial_content: str) -> str:
    """Write `initial_content` to a temporary Markdown file, open it in `$EDITOR`.

    Returns the (possibly updated) content after the editor exits. The
    temporary file is not removed until then, since Windows does not allow a
    second process to open a file that is already open.

    The editor command is taken from `$EDITOR` or `$VISUAL`. If neither is
    set, `notepad` is used on Windows and `vi` elsewhere. To use a GUI editor
    that does not block by default (e.g. VS Code), set `EDITOR="code --wait"`.
    """
    import os
    import shlex
    import subprocess
    import tempfile
    import time

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
        started = time.monotonic()
        result = subprocess.run([*shlex.split(editor), tmp_path], check=False)
        elapsed = time.monotonic() - started
        if result.returncode != 0:
            from aimbat.logger import logger

            message = (
                f"Editor '{editor}' exited with code {result.returncode}; discarding "
                + "changes."
            )
            logger.warning(message)
            print_warning(message)
            return initial_content
        with open(tmp_path, encoding="utf-8") as f:
            content = f.read()
        if content == initial_content and elapsed < 1:
            from aimbat.logger import logger

            message = (
                f"Editor '{editor}' returned in under a second with no changes - if "
                + "it launched a separate window that is still open (a non-blocking "
                + "GUI editor), any edits made there will be lost once that window "
                + "closes, since this temporary file is already gone. Use a "
                + 'wait-for-close flag, e.g. EDITOR="code --wait".'
            )
            logger.warning(message)
            print_warning(message)
        return content
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
class _PhaseContextTrait:
    """Mixin that adds optional `--phase` and `--component` arguments to a CLI command."""

    phase: Annotated[str | None, phase_parameter()] = None
    component: Annotated[str | None, component_parameter()] = None


@dataclass
class _TableParametersTrait:
    """Mixin that adds a `--raw` flag for unformatted table output."""

    raw: bool = False


@dataclass
class _YesTrait:
    """Mixin that adds a `--yes`/`-y` flag to skip a destructive-action confirmation prompt."""

    yes: Annotated[
        bool,
        Parameter(
            name=["--yes", "-y"],
            help="Skip the confirmation prompt.",
        ),
    ] = False


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
class PhaseDebugParameters(_DebugTrait, _PhaseContextTrait, _EventContextTrait):
    """Parameters for commands that operate on one phase, with optional debug mode."""

    def phase_id(self) -> UUID:
        """Resolve the event and phase given to the ID of the phase."""
        return resolve_phase_option(self.event_id, self.phase, self.component)


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
class ConfirmParameters(_YesTrait, _DebugTrait):
    """Shared parameters for destructive commands (`--yes`, `--debug`)."""

    pass


@Parameter(name="*")
@dataclass
class IccsPlotParameters:
    """Shared parameters for ICCS plot commands (`--context`, `--all`)."""

    context: Annotated[
        bool,
        Parameter(
            help=(
                "Plot seismograms with extra context instead of the short tapered "
                + "ones used for cross-correlation"
            )
        ),
    ] = True
    all_seismograms: Annotated[
        bool,
        Parameter(
            name="all",
            help="Include all seismograms in the plot, even if not used in stack.",
        ),
    ] = False
