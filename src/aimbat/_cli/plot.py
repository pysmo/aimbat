"""Create plots for seismograms and ICCS results.

Available plots:

- **data**: raw seismograms sorted by epicentral distance
- **stack**: the ICCS cross-correlation stack for the default event
- **image**: seismograms displayed as a 2-D image (wiggle plot)

Most plot commands support `--context` / `--no-context` to toggle extra
waveform context, and `--all` to include de-selected seismograms.
"""

from cyclopts import App

from .common import (
    GlobalParameters,
    IccsPlotParameters,
    simple_exception,
)

app = App(name="plot", help=__doc__, help_format="markdown")


@app.command(name="data")
@simple_exception
def cli_seismogram_plot(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot raw seismograms for the default event sorted by epicentral distance."""
    from sqlmodel import Session

    from aimbat.core import plot_all_seismograms, resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        plot_all_seismograms(session, event, return_fig=False)


@app.command(name="stack")
@simple_exception
def cli_iccs_plot_stack(
    *,
    iccs_parameters: IccsPlotParameters = IccsPlotParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot the ICCS stack of an event."""
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, plot_stack, resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        iccs = create_iccs_instance(session, event).iccs
        plot_stack(iccs, iccs_parameters.context, iccs_parameters.all, return_fig=False)


@app.command(name="image")
@simple_exception
def cli_iccs_plot_image(
    *,
    iccs_parameters: IccsPlotParameters = IccsPlotParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Plot the ICCS seismograms of an event as an image."""
    from sqlmodel import Session

    from aimbat.core import (
        create_iccs_instance,
        plot_iccs_seismograms,
        resolve_event,
    )
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        iccs = create_iccs_instance(session, event).iccs
        plot_iccs_seismograms(
            iccs, iccs_parameters.context, iccs_parameters.all, return_fig=False
        )


if __name__ == "__main__":
    app()
