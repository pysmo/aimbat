"""
Utilities for AIMBAT

The utils subcommand contains useful tools that
are not strictly part of an AIMBAT workflow.
"""

from aimbat.lib.common import debug_callback
from aimbat.cli.utils.sampledata import app as sampledata_app
from pathlib import Path
from typing import Annotated
import typer


def _run_checks(sacfiles: list[Path]) -> None:
    from aimbat.lib.utils.checkdata import run_checks

    run_checks(sacfiles)


def _plotseis(db_url: str | None, event_id: int, use_qt: bool = False) -> None:
    from aimbat.lib.utils.plotseis import plotseis
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session
    import pyqtgraph as pg  # type: ignore

    if use_qt:
        pg.mkQApp()

    with Session(engine_from_url(db_url)) as session:
        plotseis(session, event_id, use_qt)

    if use_qt:
        pg.exec()


app = typer.Typer(
    name="utils",
    no_args_is_help=True,
    callback=debug_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)
app.add_typer(sampledata_app, name="sampledata")


@app.command("checkdata")
def checkdata_cli(
    sacfiles: Annotated[list[Path], typer.Argument(help="One or more SAC files.")],
) -> None:
    """Check if there are any problems with SAC files before adding them to a project."""
    _run_checks(sacfiles)


@app.command("plotseis")
def utils_cli_plotseis(
    ctx: typer.Context,
    event_id: Annotated[
        int, typer.Argument(help="Event ID as stored in the AIMBAT project.")
    ],
) -> None:
    """Plot seismograms for an event."""

    db_url: str = ctx.obj.get("DB_URL")
    use_qt: bool = ctx.obj.get("USE_QT", False)
    _plotseis(db_url, event_id, use_qt)


if __name__ == "__main__":
    app()
