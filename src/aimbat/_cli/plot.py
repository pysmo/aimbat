"""Create plots for seismograms and ICCS results.

Available plots:

- **data**: raw seismograms sorted by epicentral distance.
- **stack**: the ICCS cross-correlation stack for an event.
- **matrix**: seismograms displayed as a matrix image.

Most plot commands support `--context` / `--no-context` to toggle extra
waveform context, and `--all` to include deselected seismograms.

`stack` and `matrix` build an ICCS instance to plot from, which writes the
resulting cross-correlation values to the project database (the same
live-quality write every ICCS-consuming command makes) - despite being
read-only from the user's point of view, they do write to the database.
"""

from typing import Annotated
from uuid import UUID

from cyclopts import App

from .common import (
    DebugParameter,
    IccsPlotParameters,
    event_parameter,
    handle_issues,
)

app = App(name="plot", help=__doc__, help_format="markdown")


@app.command(name="seismograms")
@handle_issues
def cli_seismogram_plot(
    event_id: Annotated[UUID, event_parameter()],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Plot input seismograms in an event sorted by epicentral distance."""
    from sqlmodel import Session

    from aimbat.core import resolve_event
    from aimbat.db import engine
    from aimbat.plot import plot_seismograms

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        plot_seismograms(event, return_fig=False)


@app.command(name="stack")
@handle_issues
def cli_plot_stack(
    event_id: Annotated[UUID, event_parameter()],
    *,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    _: DebugParameter = DebugParameter(),
) -> None:
    """Plot the ICCS stack of an event.

    Building the ICCS instance writes each seismogram's cross-correlation
    value to the project database, so this command writes to the database
    despite being read-only from the user's point of view.
    """
    from sqlmodel import Session

    from aimbat.core import create_iccs_instance, resolve_event
    from aimbat.db import engine
    from aimbat.plot import plot_stack

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        iccs = create_iccs_instance(session, event).iccs
        plot_stack(
            iccs,
            iccs_plot_parameters.context,
            all_seismograms=iccs_plot_parameters.all_seismograms,
            return_fig=False,
        )


@app.command(name="matrix")
@handle_issues
def cli_plot_matrix_image(
    event_id: Annotated[UUID, event_parameter()],
    *,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    _: DebugParameter = DebugParameter(),
) -> None:
    """Plot the ICCS seismograms of an event as a matrix image.

    The matrix is assembled from individual waveforms, with each row
    representing a different seismogram. Building the ICCS instance writes
    each seismogram's cross-correlation value to the project database, so
    this command writes to the database despite being read-only from the
    user's point of view.
    """
    from sqlmodel import Session

    from aimbat.core import (
        create_iccs_instance,
        resolve_event,
    )
    from aimbat.db import engine
    from aimbat.plot import plot_matrix_image

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        iccs = create_iccs_instance(session, event).iccs
        plot_matrix_image(
            iccs,
            iccs_plot_parameters.context,
            all_seismograms=iccs_plot_parameters.all_seismograms,
            return_fig=False,
        )


if __name__ == "__main__":
    app()
