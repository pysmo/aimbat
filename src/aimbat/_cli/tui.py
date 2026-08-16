"""Launch the AIMBAT terminal user interface."""

from cyclopts import App

from .common import DebugParameter, handle_issues

app = App(name="tui", help=__doc__, help_format="markdown")


@app.default
@handle_issues
def cli_tui(*, _: DebugParameter = DebugParameter()) -> None:
    """Launch the AIMBAT terminal user interface."""
    import warnings

    from aimbat._tui.app import main
    from aimbat.core._migrations import SchemaStaleWarning

    # The TUI has its own complete handling for a stale schema - a blocking
    # modal built in on_mount() directly from _build_staleness_warning, not
    # from the warnings module at all. AimbatTUI().run() blocks for the
    # whole session, so handle_issues's CLI-wide SchemaStaleWarning-to-error
    # promotion would otherwise still be active when on_mount()'s first DB
    # connection fires first_connect, crashing before the modal logic ever
    # runs. Scoped to this call only; restored automatically on exit.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SchemaStaleWarning)
        main()
