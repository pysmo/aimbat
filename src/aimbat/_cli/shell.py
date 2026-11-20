"""Interactive AIMBAT shell with tab-completion and command history.

All CLI commands are available. Press Tab to complete commands, options
and IDs, Ctrl+D or type `exit` to leave.

Shell-only commands:
  event switch [ID]    Switch the shell's event context.
  phase switch [NAME]  Switch the shell's phase context.
"""

import uuid
from typing import TYPE_CHECKING, Annotated

from cyclopts import App

from .common import (
    DebugParameter,
    event_parameter,
    handle_issues,
    phase_parameter,
    print_error_panel,
    resolve_phase_option,
)

if TYPE_CHECKING:
    from rich.console import Console

    from aimbat._cli._shell_completer import ShellCompleter
    from aimbat.core import BoundICCS

app = App(name="shell", help=__doc__, help_format="markdown")

type _CompletionDict = dict[str, "_CompletionDict | None"]


def _build_completion_dict(cyclopts_app: App) -> _CompletionDict:
    """Recursively build a NestedCompleter dict from a cyclopts app tree."""
    skip: set[str] = set(cyclopts_app.help_flags)
    if hasattr(cyclopts_app, "version_flags"):
        skip.update(cyclopts_app.version_flags)
    result: _CompletionDict = {}

    # Flags from this app's own default command.
    if cyclopts_app.default_command is not None:
        for arg in cyclopts_app.assemble_argument_collection():
            if arg.show:
                for flag in arg.names:
                    if flag.startswith("-") and flag not in skip:
                        result[flag] = None

    # Subcommands (recurse).
    for name in cyclopts_app:
        if name in skip:
            continue
        sub = cyclopts_app[name]
        nested = _build_completion_dict(sub)
        result[name] = nested if nested else None
    return result


def _shell_completer(cyclopts_app: App) -> "ShellCompleter":
    """Return the shell's tab completer, with shell-only commands added.

    Commands that make no sense inside the shell (`shell`, `tui` and
    `utils completion`) are left out, and `event switch`, `phase switch` and
    `exit` are added.
    """
    from prompt_toolkit.completion import NestedCompleter

    from aimbat.models import AimbatEvent

    from ._shell_completer import ShellCompleter
    from .common import PhaseNameConverter, UuidConverter

    completion_dict = _build_completion_dict(cyclopts_app)
    completion_dict.pop("shell", None)
    completion_dict.pop("tui", None)
    utils_completions = completion_dict.get("utils")
    if isinstance(utils_completions, dict):
        utils_completions.pop("completion", None)
    event_completions = completion_dict.get("event")
    if isinstance(event_completions, dict):
        event_completions["switch"] = None
    phase_completions = completion_dict.get("phase")
    if isinstance(phase_completions, dict):
        phase_completions["switch"] = None
    completion_dict["exit"] = None

    return ShellCompleter(
        cyclopts_app,
        NestedCompleter.from_nested_dict(completion_dict),
        shell_only={
            ("event", "switch"): UuidConverter(AimbatEvent),
            ("phase", "switch"): PhaseNameConverter(),
        },
    )


def _extract_event_flag(tokens: list[str]) -> str | None:
    """Return the value of --event / --event-id from a token list, or None."""
    flags = {"--event", "--event-id"}
    for i, tok in enumerate(tokens):
        if tok in flags and i + 1 < len(tokens):
            return tokens[i + 1]
        for flag in flags:
            if tok.startswith(f"{flag}="):
                return tok.split("=", 1)[1]
    return None


def _parse_event_id(value: str) -> uuid.UUID:
    """Parse a full UUID or unique prefix into a UUID.

    Mirrors the --event converter used by CLI commands so that `event switch`
    accepts the same shortened prefixes.
    """
    try:
        return uuid.UUID(value)
    except ValueError:
        from sqlmodel import Session

        from aimbat.db import engine
        from aimbat.models import AimbatEvent
        from aimbat.utils import string_to_uuid

        with Session(engine) as session:
            return string_to_uuid(session, value, AimbatEvent)


def _has_phase(event_id: uuid.UUID, name: str) -> bool:
    """Return whether an event has a phase of that name."""
    from sqlalchemy.exc import NoResultFound

    try:
        resolve_phase_option(event_id, name)
    except NoResultFound:
        return False
    return True


def _only_phase_name(event_id: uuid.UUID) -> str | None:
    """Return the name of an event's only phase, or None if it has none or several."""
    from sqlalchemy.exc import NoResultFound
    from sqlmodel import Session

    from aimbat.core import AmbiguousPhaseError, resolve_phase
    from aimbat.db import engine

    try:
        with Session(engine) as session:
            return resolve_phase(session, event_id).name
    except (NoResultFound, AmbiguousPhaseError):
        return None


def _check_iccs(
    console: "Console",
    prev: "BoundICCS | None",
    *,
    startup: bool = False,
    event_id: uuid.UUID | None = None,
) -> "BoundICCS | None":
    """Query ICCS status and print a line only when something changes.

    On startup (`startup=True`) always prints.  On subsequent calls prints only
    when status changes: stale cache rebuilt, event changed, ICCS became invalid,
    or recovered. The phase is the one named by `DEFAULT_PHASE`, or the
    event's only phase.

    Args:
        console: Rich console for output.
        prev: The BoundICCS from the previous check, or None.
        startup: If True, always print regardless of previous state.
        event_id: Event to check ICCS for.

    Returns:
        The current BoundICCS, or None if unavailable.
    """
    import os

    from sqlalchemy.exc import NoResultFound

    from aimbat.actions import prepare_iccs

    try:
        if event_id is None:
            raise NoResultFound("No event specified.")
        phase = os.environ.get("DEFAULT_PHASE") or None
        bound = prepare_iccs(resolve_phase_option(event_id, phase))
        changed = prev is None or prev.phase_id != bound.phase_id or bound is not prev
        if startup or changed:
            where = f"event {str(event_id)[:8]}"
            if phase is not None:
                where += f", phase {phase}"
            console.print(f"[green]ICCS ready[/green] ({where})")
        return bound
    except Exception as exc:
        if startup or prev is not None:
            # startup: always report; post-command: only report on transition
            console.print(f"[yellow]ICCS not ready[/yellow]: {exc}")
        return None


@app.default
@handle_issues
def cli_shell(
    event_id: Annotated[
        uuid.UUID | None,
        event_parameter(
            help=(
                "Start the shell in the context of a specific event. Full UUID or any"
                + " unique prefix as shown in the table. "
            )
        ),
    ] = None,
    *,
    phase: Annotated[
        str | None,
        phase_parameter(
            help=(
                "Start the shell in the context of a phase of that event. Not needed"
                + " when the event has only one phase."
            )
        ),
    ] = None,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Start an interactive AIMBAT shell."""
    import os
    import shlex
    from pathlib import Path

    from cyclopts import CycloptsError
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from rich.console import Console

    from aimbat.app import app as aimbat_app

    console = Console()

    # Shell-local event and phase context, None if not specified.
    # Modified by `event switch` and `phase switch`.
    shell_event_id: uuid.UUID | None = event_id
    shell_phase: str | None = phase

    # Propagate the shell event context to commands via the DEFAULT_EVENT_ID env
    # var, which all event_parameter() / event_parameter_with_all() converters
    # pick up as a fallback.  Explicit --event flags always take precedence.
    _prev_default_event = os.environ.get("DEFAULT_EVENT_ID")
    _prev_default_phase = os.environ.get("DEFAULT_PHASE")

    def _set_shell_phase(name: str | None) -> None:
        nonlocal shell_phase
        shell_phase = name
        if name is not None:
            os.environ["DEFAULT_PHASE"] = name
        else:
            os.environ.pop("DEFAULT_PHASE", None)

    if phase is not None:
        _set_shell_phase(phase)

    def _set_shell_event(eid: uuid.UUID | None) -> None:
        nonlocal shell_event_id
        shell_event_id = eid
        if eid is not None:
            os.environ["DEFAULT_EVENT_ID"] = str(eid)
        else:
            os.environ.pop("DEFAULT_EVENT_ID", None)

    _set_shell_event(shell_event_id)

    import sys

    completer = _shell_completer(aimbat_app)
    pt_session: PromptSession[str] | None = None
    if sys.stdin.isatty():
        pt_session = PromptSession(
            history=FileHistory(str(Path.home() / ".aimbat_history")),
            completer=completer,
            complete_while_typing=True,
        )

    console.print(
        "[bold]AIMBAT shell[/bold]  (Tab to complete, Ctrl+D or "
        + "[bold]exit[/bold] to quit)"
    )

    current_bound = _check_iccs(console, None, startup=True, event_id=shell_event_id)

    def _prompt() -> str:
        if shell_event_id is None:
            return "aimbat> "
        context = str(shell_event_id)[:8]
        if shell_phase is not None:
            context += f"/{shell_phase}"
        return f"aimbat [{context}]> "

    try:
        while True:
            try:
                if pt_session is not None:
                    text = pt_session.prompt(_prompt).strip()
                else:
                    raw = sys.stdin.readline()
                    if not raw:
                        break
                    text = raw.strip()
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

            if not text:
                continue
            # Commands can add or delete records, so re-read IDs next time.
            completer.invalidate()
            if text in ("exit", "quit", "q"):
                break

            try:
                tokens = shlex.split(text)
            except ValueError as exc:
                console.print(f"[red]Parse error:[/red] {exc}")
                continue

            # Strip a leading "aimbat" token typed out of habit and remind the user.
            if tokens and tokens[0] == "aimbat":
                tokens = tokens[1:]
                console.print("[dim]Tip: no need to type 'aimbat' in the shell.[/dim]")
                if not tokens:
                    continue

            # Shell-only: "event switch [id]" changes context.
            if tokens[:2] == ["event", "switch"]:
                if len(tokens) < 3:
                    # No argument: clear shell event context.
                    _set_shell_event(None)
                    current_bound = _check_iccs(
                        console, None, startup=True, event_id=None
                    )
                else:
                    try:
                        new_event_id = _parse_event_id(tokens[2])
                        if shell_phase is not None:
                            if not _has_phase(new_event_id, shell_phase):
                                console.print(
                                    f"[dim]The event has no phase {shell_phase!r}."
                                    + " The phase context is cleared.[/dim]"
                                )
                                _set_shell_phase(None)
                        elif shell_event_id is not None:
                            # The previous event's only phase carries over too.
                            carried = _only_phase_name(shell_event_id)
                            if carried is not None and _has_phase(
                                new_event_id, carried
                            ):
                                _set_shell_phase(carried)
                        _set_shell_event(new_event_id)
                        current_bound = _check_iccs(
                            console, None, startup=True, event_id=shell_event_id
                        )
                    except Exception as exc:
                        print_error_panel(exc)
                continue

            # Shell-only: "phase switch [name]" changes the phase context.
            if tokens[:2] == ["phase", "switch"]:
                try:
                    if len(tokens) < 3:
                        _set_shell_phase(None)
                    elif shell_event_id is None:
                        raise ValueError(
                            "A phase is switched within an event."
                            + " `event switch` sets the event first."
                        )
                    else:
                        # Raises with the event's phases if it has no such phase.
                        resolve_phase_option(shell_event_id, tokens[2])
                        _set_shell_phase(tokens[2])
                    current_bound = _check_iccs(
                        console, None, startup=True, event_id=shell_event_id
                    )
                except Exception as exc:
                    print_error_panel(exc)
                continue

            try:
                aimbat_app(tokens, exit_on_error=False)

                # Check ICCS for the event targeted by the command.  If the
                # user passed --event all (or no explicit flag), fall back to
                # the shell context event.
                explicit_flag = _extract_event_flag(tokens)
                check_event_id: uuid.UUID | None
                if explicit_flag and explicit_flag.lower() != "all":
                    check_event_id = _parse_event_id(explicit_flag)
                else:
                    check_event_id = shell_event_id
                current_bound = _check_iccs(
                    console, current_bound, event_id=check_event_id
                )
            except (CycloptsError, SystemExit):
                # Errors already printed by Cyclopts or subcommand
                pass
            except Exception as exc:
                print_error_panel(exc)
    finally:
        # Restore DEFAULT_EVENT_ID to whatever it was before the shell started.
        if _prev_default_event is not None:
            os.environ["DEFAULT_EVENT_ID"] = _prev_default_event
        else:
            os.environ.pop("DEFAULT_EVENT_ID", None)
        if _prev_default_phase is not None:
            os.environ["DEFAULT_PHASE"] = _prev_default_phase
        else:
            os.environ.pop("DEFAULT_PHASE", None)
