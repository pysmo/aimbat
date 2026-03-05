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
    simple_exception,
)
from cyclopts import App

app = App(name="plot", help=__doc__, help_format="markdown")


@app.command(name="data")
@simple_exception
def cli_seismogram_plot(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot raw seismograms for the active event sorted by epicentral distance."""
    from aimbat.db import engine
    from aimbat.core import plot_all_seismograms, get_active_event
    from sqlmodel import Session

    with Session(engine) as session:
        active_event = get_active_event(session)
        plot_all_seismograms(session, active_event, return_fig=False)


@app.command(name="stack")
@simple_exception
def cli_iccs_plot_stack(
    *,
    iccs_parameters: IccsPlotParameters = IccsPlotParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot the ICCS stack of the active event."""
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, plot_stack, get_active_event
    from sqlmodel import Session

    with Session(engine) as session:
        active_event = get_active_event(session)
        iccs = create_iccs_instance(session, active_event).iccs
        plot_stack(iccs, iccs_parameters.context, iccs_parameters.all, return_fig=False)


@app.command(name="image")
@simple_exception
def cli_iccs_plot_image(
    *,
    iccs_parameters: IccsPlotParameters = IccsPlotParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot the ICCS seismograms of the active event as an image."""
    from aimbat.db import engine
    from aimbat.core import (
        create_iccs_instance,
        plot_iccs_seismograms,
        get_active_event,
    )
    from sqlmodel import Session

    with Session(engine) as session:
        active_event = get_active_event(session)
        iccs = create_iccs_instance(session, active_event).iccs
        plot_iccs_seismograms(
            iccs, iccs_parameters.context, iccs_parameters.all, return_fig=False
        )


if __name__ == "__main__":
    app()
