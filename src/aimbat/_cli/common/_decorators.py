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
    """Decorator to report exceptions to the console and exit cleanly.

    Exceptions are printed (without traceback) in a red panel, then exit the
    process. Any `aimbat.core.SchemaStaleWarning` raised during the call
    (e.g. via `aimbat.db`'s schema-staleness check) is unconditionally
    promoted to an error via a `warnings.catch_warnings()`-scoped filter, so
    it's reported through the exact same red-panel path as any other
    failure - a stale schema always aborts the command with one clear,
    attributable message, rather than sometimes silently continuing (if the
    command never happens to touch the drifted table/column) and sometimes
    crashing later with a raw, unrelated `sqlalchemy.exc.OperationalError`
    from deep inside whatever query first hit it. This is independent of
    `AIMBAT_STRICT_SCHEMA_CHECK`, which now only affects third-party code
    using `aimbat.db.engine` directly, not AIMBAT's own CLI - see that
    setting's description and `aimbat.db`'s module docstring.

    The filter is scoped to `SchemaStaleWarning` specifically (not a blanket
    `simplefilter`), so it can't affect any other warning category's
    already-ambient filter/display behaviour, and `aimbat db upgrade`'s own
    `warnings.simplefilter("ignore", SchemaStaleWarning)` (telling a user to
    run the command they're already running is unhelpful) still takes
    precedence within its own nested `catch_warnings()` block.

    The `SchemaStaleWarning` promotion applies even in debugging mode
    (`AIMBAT_LOG_LEVEL=DEBUG`/`TRACE`) - a stale schema must always abort,
    with no bypass. What debugging mode *does* skip is the try/except that
    turns any exception (including the now-promoted `SchemaStaleWarning`)
    into a styled red panel: in that mode the exception instead propagates
    as a plain Python traceback, exactly as any other exception would.
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
