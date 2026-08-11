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
    """Decorator to report exceptions and non-fatal warnings to the console.

    Exceptions are printed (without traceback) in a red panel, then exit the
    process. Any `aimbat.core.SchemaStaleWarning` raised during the call
    (e.g. via `aimbat.db`'s schema-staleness check) is printed as a styled,
    non-blocking message instead - it doesn't stop the command, and doesn't
    need `aimbat.db` to touch `warnings.showwarning` globally to look right;
    this decorator supplies that scoped to just the CLI command's own call
    via `warnings.catch_warnings()`. Only `SchemaStaleWarning` is
    intercepted - any other warning raised during the call is passed
    through to whatever `showwarning` was already in effect, completely
    unaffected by this decorator. `AIMBAT_STRICT_SCHEMA_CHECK` still reaches
    the exception branch as normal, since promoting a warning to an error
    happens during Python's filter matching, before it would ever reach
    `showwarning` at all.

    In debugging mode (`AIMBAT_LOG_LEVEL=DEBUG`/`TRACE`) this decorator
    returns the callable unchanged - both exceptions and warnings then
    behave exactly as plain Python would, untouched by this decorator.
    """
    import sys
    import warnings
    from functools import wraps

    from aimbat.core._migrations import SchemaStaleWarning

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if settings.log_level in ("TRACE", "DEBUG"):
            return func(*args, **kwargs)
        try:
            passthrough_showwarning = warnings.showwarning

            def _display_or_pass_through(  # type: ignore[no-untyped-def]
                message, category, filename, lineno, file=None, line=None
            ) -> None:
                # Printed immediately, at the point the warning actually
                # fires (typically the command's first DB connection,
                # before its own output), rather than collected and shown
                # after `func()` returns - the latter would print the
                # warning after any output `func()` itself already
                # produced, which reads oddly since the underlying
                # condition was detected first.
                if issubclass(category, SchemaStaleWarning):
                    _print_warning(message)
                else:
                    passthrough_showwarning(
                        message, category, filename, lineno, file, line
                    )

            # Deliberately does *not* install its own filter rule (e.g.
            # `simplefilter("always", ...)`) - `simplefilter` prepends,
            # which would take priority over and silently defeat the
            # "error" filter `AIMBAT_STRICT_SCHEMA_CHECK` installs. Relying
            # on whatever filter is already ambient is correct here: the
            # default action already shows a first-time-per-location
            # warning (our warning only ever fires once per process, via
            # `first_connect`), and an "error" filter still takes effect
            # and raises before `showwarning` is ever reached.
            with warnings.catch_warnings():
                warnings.showwarning = _display_or_pass_through
                result = func(*args, **kwargs)

            return result
        except Exception as e:
            print_error_panel(e)
            sys.exit(1)

    return wrapper  # type: ignore
