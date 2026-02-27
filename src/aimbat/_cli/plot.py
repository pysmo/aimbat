"""Create plots for seismograms and ICCS results.

Available plots:

- **data**: raw seismograms sorted by epicentral distance
- **stack**: the ICCS cross-correlation stack for the active event
- **image**: seismograms displayed as a 2-D image (wiggle plot)

Most plot commands support `--context` / `--no-context` to toggle extra
waveform context, and `--all` to include de-selected seismograms.
"""

from .common import (
    GlobalParameters,
    IccsPlotParameters,
    PlotParameters,
    simple_exception,
)
from cyclopts import App

app = App(name="plot", help=__doc__, help_format="markdown")


@app.command(name="data")
@simple_exception
def cli_seismogram_plot(
    *,
    plot_parameters: PlotParameters = PlotParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot raw seismograms for the active event sorted by epicentral distance."""
    from aimbat.db import engine
    from aimbat.core import plot_all_seismograms
    from sqlmodel import Session
    import pyqtgraph as pg  # type: ignore

    if plot_parameters.use_qt:
        pg.mkQApp()

    with Session(engine) as session:
        plot_all_seismograms(session, plot_parameters.use_qt)

    if plot_parameters.use_qt:
        pg.exec()


@app.command(name="stack")
@simple_exception
def cli_iccs_plot_stack(
    *,
    iccs_parameters: IccsPlotParameters = IccsPlotParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot the ICCS stack of the active event."""
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, plot_stack
    from sqlmodel import Session

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        plot_stack(iccs, iccs_parameters.context, iccs_parameters.all)


@app.command(name="image")
@simple_exception
def cli_iccs_plot_image(
    *,
    iccs_parameters: IccsPlotParameters = IccsPlotParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot the ICCS seismograms of the active event as an image."""
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, plot_iccs_seismograms
    from sqlmodel import Session

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        plot_iccs_seismograms(iccs, iccs_parameters.context, iccs_parameters.all)


if __name__ == "__main__":
    app()
