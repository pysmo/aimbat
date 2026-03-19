"""Interactive AIMBAT shell with tab-completion and command history.

All CLI commands are available. Press Tab to complete commands, Ctrl+D
or type `exit` to leave.

Shell-only commands:
  event switch [ID]  Switch the shell's event context.
"""

import uuid
from typing import TYPE_CHECKING, Annotated

from cyclopts import App

from .common import (
    DebugParameter,
    event_parameter,
    print_error_panel,
    simple_exception,
)

if TYPE_CHECKING:
    from rich.console import Console

    from aimbat.core import BoundICCS

app = App(name="shell", help=__doc__, help_format="markdown")


def _build_completion_dict(cyclopts_app: App) -> dict[str, dict | None]:
    """Recursively build a NestedCompleter dict from a cyclopts app tree."""
    skip: set[str] = set(cyclopts_app.help_flags)
    if hasattr(cyclopts_app, "version_flags"):
        skip.update(cyclopts_app.version_flags)
    result: dict[str, dict | None] = {}

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
    or recovered.

    Args:
        console: Rich console for output.
        prev: The BoundICCS from the previous check, or None.
        startup: If True, always print regardless of previous state.
        event_id: Event to check ICCS for.

    Returns:
        The current BoundICCS, or None if unavailable.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event
    from aimbat.db import engine

    try:
        with Session(engine) as session:
            event = resolve_event(session, event_id)
            bound = create_iccs_instance(session, event)
        changed = (
            prev is None
            or prev.event_id != bound.event_id
            or bound.created_at != prev.created_at
        )
        if startup or changed:
            console.print(f"[green]ICCS ready[/green] (event {str(event.id)[:8]})")
        return bound
    except Exception as exc:
        if startup or prev is not None:
            # startup: always report; post-command: only report on transition
            console.print(f"[yellow]ICCS not ready[/yellow] — {exc}")
        return None


@app.default
@simple_exception
def cli_shell(
    event_id: Annotated[
        uuid.UUID | None,
        event_parameter(
            help="Start the shell in the context of a specific event. "
            "Full UUID or any unique prefix as shown in the table. "
        ),
    ] = None,
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Start an interactive AIMBAT shell."""
    import os
    import shlex
    from pathlib import Path

    from cyclopts import CycloptsError
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import NestedCompleter
    from prompt_toolkit.history import FileHistory
    from rich.console import Console

    from aimbat.app import app as aimbat_app

    console = Console()

    # Shell-local event context — None if no event specified.
    # Modified by `event switch`.
    shell_event_id: uuid.UUID | None = event_id

    # Propagate the shell event context to commands via the DEFAULT_EVENT_ID env
    # var, which all event_parameter() / event_parameter_with_all() converters
    # pick up as a fallback.  Explicit --event flags always take precedence.
    _prev_default_event = os.environ.get("DEFAULT_EVENT_ID")

    def _set_shell_event(eid: uuid.UUID | None) -> None:
        nonlocal shell_event_id
        shell_event_id = eid
        if eid is not None:
            os.environ["DEFAULT_EVENT_ID"] = str(eid)
        else:
            os.environ.pop("DEFAULT_EVENT_ID", None)

    _set_shell_event(shell_event_id)

    completion_dict = _build_completion_dict(aimbat_app)
    completion_dict.pop("shell", None)
    completion_dict.pop("tui", None)

    # Inject the shell-only `event switch` subcommand into tab completion.
    event_completions = completion_dict.get("event")
    if isinstance(event_completions, dict):
        event_completions["switch"] = None

    import sys

    pt_session: PromptSession[str] | None = None
    if sys.stdin.isatty():
        pt_session = PromptSession(
            history=FileHistory(str(Path.home() / ".aimbat_history")),
            completer=NestedCompleter.from_nested_dict(completion_dict),
            complete_while_typing=True,
        )

    console.print(
        "[bold]AIMBAT shell[/bold]  (Tab to complete, Ctrl+D or [bold]exit[/bold] to quit)"
    )

    current_bound = _check_iccs(console, None, startup=True, event_id=shell_event_id)

    def _prompt() -> str:
        if shell_event_id is not None:
            return f"aimbat [{str(shell_event_id)[:8]}]> "
        return "aimbat> "

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

            # Shell-only: event switch [id]  — changes context.
            if tokens[:2] == ["event", "switch"]:
                if len(tokens) < 3:
                    # No argument: clear shell event context.
                    _set_shell_event(None)
                    current_bound = _check_iccs(
                        console, None, startup=True, event_id=None
                    )
                else:
                    try:
                        _set_shell_event(_parse_event_id(tokens[2]))
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
