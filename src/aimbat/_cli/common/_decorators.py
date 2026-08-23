"""Console error/warning helpers and the `handle_issues` command decorator."""

from collections.abc import Callable
from typing import Any

from aimbat import settings

__all__ = ["print_error_panel", "handle_issues"]


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


def _print_warning(message: object) -> None:
    """Print a non-fatal warning message to the console, styled yellow."""
    from rich.console import Console
    from rich.text import Text

    # A `Text` object applies styling structurally rather than via markup
    # tags, so a `[`/`]` in the message (e.g. a future revision id, built
    # from database content) can't be misinterpreted as Rich markup.
    Console(stderr=True).print(Text(str(message), style="yellow"))


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
    import sys
    import warnings
    from functools import wraps

    from aimbat.core._migrations import SchemaStaleWarning

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with warnings.catch_warnings():
            warnings.filterwarnings("error", category=SchemaStaleWarning)

            if settings.log_level in ("TRACE", "DEBUG"):
                return func(*args, **kwargs)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                print_error_panel(e)
                sys.exit(1)

    return wrapper  # type: ignore
