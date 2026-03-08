"""Create plots for seismograms and ICCS results.

Available plots:

- **data**: raw seismograms sorted by epicentral distance.
- **stack**: the ICCS cross-correlation stack for an event.
- **matrix**: seismograms displayed as a matrix image.

Most plot commands support `--context` / `--no-context` to toggle extra
waveform context, and `--all` to include deselected seismograms.
"""

from cyclopts import App

from .common import GlobalParameters, IccsPlotParameters, simple_exception

app = App(name="plot", help=__doc__, help_format="markdown")


@app.command(name="seismograms")
@simple_exception
def cli_seismogram_plot(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot input seismograms in an event sorted by epicentral distance."""
    from sqlmodel import Session

    from aimbat.core import resolve_event
    from aimbat.db import engine
    from aimbat.plot import plot_seismograms

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        plot_seismograms(session, event, return_fig=False)


@app.command(name="stack")
@simple_exception
def cli_plot_stack(
    *,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot the ICCS stack of an event."""
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event
    from aimbat.db import engine
    from aimbat.plot import plot_stack

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        iccs = create_iccs_instance(session, event).iccs
        plot_stack(
            iccs,
            iccs_plot_parameters.context,
            all_seismograms=iccs_plot_parameters.all_seismograms,
            return_fig=False,
        )


@app.command(name="matrix")
@simple_exception
def cli_plot_matrix_image(
    *,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot the ICCS seismograms of an event as a matrix image.

    The matrix is assembled from individual waveforms, with each row
    representing a different seismogram.
    """
    from sqlmodel import Session

    from aimbat.core import (
        create_iccs_instance,
        resolve_event,
    )
    from aimbat.db import engine
    from aimbat.plot import plot_matrix_image

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        iccs = create_iccs_instance(session, event).iccs
        plot_matrix_image(
            iccs,
            iccs_plot_parameters.context,
            all_seismograms=iccs_plot_parameters.all_seismograms,
            return_fig=False,
        )


if __name__ == "__main__":
    app()
