"""Console error/warning helpers and the `handle_issues` command decorator."""

from collections.abc import Callable
from typing import Any

from aimbat import settings

__all__ = [
    "confirm_or_abort",
    "handle_issues",
    "print_error_panel",
    "print_warning",
    "run_reporting_issues",
]


def print_error_panel(e: Exception) -> None:
    """Print an exception to the console in a red panel."""
    from rich.console import Console
    from rich.panel import Panel

    from aimbat.utils import exception_message

    console = Console(stderr=True)
    panel = Panel(
        exception_message(e)
        + "\n\n(run with --debug or AIMBAT_LOG_LEVEL=DEBUG for a full traceback)",
        title="Error",
        title_align="left",
        border_style="red",
        expand=True,
    )
    console.print(panel)


def print_warning(message: object) -> None:
    """Print a non-fatal warning message to the console, styled yellow."""
    from rich.console import Console
    from rich.text import Text

    # A `Text` object applies styling structurally rather than via markup
    # tags, so a `[`/`]` in the message (e.g. a future revision id, built
    # from database content) can't be misinterpreted as Rich markup.
    Console(stderr=True).print(Text(str(message), style="yellow"))


def run_reporting_issues[T](func: Callable[[], T]) -> T:
    """Run `func`, reporting exceptions to the console the same way `handle_issues` does.

    Exists so code that runs outside a `handle_issues`-wrapped command body -
    currently the UUID-prefix converters in `common/_parameters.py`, which
    cyclopts calls during argument parsing, before the command function
    itself is invoked - gets the same styled-panel / debug-mode-passthrough
    behaviour instead of a raw, unstyled traceback.

    Any `aimbat.core.SchemaStaleWarning` raised during the call is always
    promoted to an error first, so a stale database schema is reported
    through the same red-panel path as any other failure, regardless of
    `AIMBAT_STRICT_SCHEMA_CHECK`.

    In debugging mode (`AIMBAT_LOG_LEVEL=DEBUG`/`TRACE`, or a `--debug` flag
    on the command line), the schema staleness promotion still applies, but
    exceptions are no longer caught and rendered as a panel; they propagate
    as a normal Python traceback instead.

    A converter runs while cyclopts is still parsing arguments, before it
    constructs the `_DebugTrait`-derived dataclass whose `__post_init__`
    would otherwise set `settings.log_level` from `--debug` - that dataclass
    is only built once every field, including this one, has already
    converted successfully. So `sys.argv` is checked directly for `--debug`
    here as well, rather than relying solely on `settings.log_level`.
    """
    import sys
    import warnings

    from aimbat.core._migrations import SchemaStaleWarning

    with warnings.catch_warnings():
        warnings.filterwarnings("error", category=SchemaStaleWarning)

        if settings.log_level in ("TRACE", "DEBUG") or "--debug" in sys.argv:
            return func()

        try:
            return func()
        except Exception as e:
            print_error_panel(e)
            sys.exit(1)


def handle_issues[F: Callable[..., Any]](func: F) -> F:
    """Decorator that reports exceptions to the console and exits cleanly.

    Exceptions raised by the wrapped command are printed (without traceback)
    in a red panel, then the process exits with status 1. Any
    `aimbat.core.SchemaStaleWarning` raised during the call is always
    promoted to an error first, so a stale database schema is reported
    through the same red-panel path as any other failure, regardless of
    `AIMBAT_STRICT_SCHEMA_CHECK`.

    In debugging mode (`AIMBAT_LOG_LEVEL=DEBUG` or `TRACE`), the schema
    staleness promotion still applies, but exceptions are no longer caught
    and rendered as a panel; they propagate as a normal Python traceback
    instead.
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return run_reporting_issues(lambda: func(*args, **kwargs))

    return wrapper  # type: ignore[return-value]


def confirm_or_abort(message: str, *, yes: bool) -> None:
    """Prompt for confirmation before a destructive action, then abort if declined.

    Args:
        message: The Yes/No question to display.
        yes: If True, skip the prompt (for scripting/non-interactive use).

    Raises:
        SystemExit: With status 0, if the user declines or the prompt cannot
            be read (e.g. no interactive terminal is attached).
    """
    if yes:
        return

    import sys

    from rich.console import Console
    from rich.prompt import Confirm

    console = Console(stderr=True)
    try:
        confirmed = Confirm.ask(message, console=console, default=False)
    except (EOFError, KeyboardInterrupt):
        confirmed = False

    if not confirmed:
        console.print("Aborted.")
        sys.exit(0)
