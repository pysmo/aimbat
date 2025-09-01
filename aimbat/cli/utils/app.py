"""
Utilities for AIMBAT.

The utils subcommand contains useful tools that
are not strictly part of an AIMBAT workflow.
"""

from aimbat.cli.common import CommonParameters
from aimbat.cli.utils.sampledata import app as sampledata_app
from pathlib import Path
from typing import Annotated
from cyclopts import App, Parameter


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


app = App(name="utils", help=__doc__, help_format="markdown")
app.command(sampledata_app, name="sampledata")


@app.command(name="checkdata")
def checkdata_cli(
    sacfiles: Annotated[list[Path], Parameter(name="data", consume_multiple=True)],
) -> None:
    """Check if there are any problems with SAC files before adding them to a project.

    Parameters:
        sacfiles: One or more SAC files.
    """
    _run_checks(sacfiles)


@app.command(name="plotseis")
def utils_cli_plotseis(
    event_id: Annotated[int, Parameter(name="id")],
    *,
    common: CommonParameters | None = None,
) -> None:
    """Plot seismograms for an event.

    Parameters:
        event_id: Event ID as stored in the AIMBAT project.
    """

    common = common or CommonParameters()

    _plotseis(common.db_url, event_id, common.use_qt)


if __name__ == "__main__":
    app()
