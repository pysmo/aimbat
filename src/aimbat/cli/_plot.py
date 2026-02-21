"""Create various plots related to ICCS."""

from ._common import (
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
    plot_parameters: PlotParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Plot raw seismograms for the active event sorted by epicentral distance."""
    from aimbat.db import engine
    from aimbat.core import plot_all_seismograms
    from sqlmodel import Session
    import pyqtgraph as pg  # type: ignore

    global_parameters = global_parameters or GlobalParameters()

    use_qt = (plot_parameters or PlotParameters()).use_qt

    if use_qt:
        pg.mkQApp()

    with Session(engine) as session:
        plot_all_seismograms(session, use_qt)

    if use_qt:
        pg.exec()


@app.command(name="stack")
@simple_exception
def cli_iccs_plot_stack(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Plot the ICCS stack of the active event."""
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, plot_stack
    from sqlmodel import Session

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        plot_stack(iccs, iccs_parameters.context, iccs_parameters.all)


@app.command(name="image")
@simple_exception
def cli_iccs_plot_image(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Plot the ICCS seismograms of the active event as an image."""
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, plot_iccs_seismograms
    from sqlmodel import Session

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        plot_iccs_seismograms(iccs, iccs_parameters.context, iccs_parameters.all)


if __name__ == "__main__":
    app()
