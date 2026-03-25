"""Launch the AIMBAT terminal user interface."""

from cyclopts import App

from .common import DebugParameter, simple_exception

app = App(name="tui", help=__doc__, help_format="markdown")


@app.default
@simple_exception
def cli_tui(*, _: DebugParameter = DebugParameter()) -> None:
    """Launch the AIMBAT terminal user interface."""
    from aimbat._tui.app import main

    main()
