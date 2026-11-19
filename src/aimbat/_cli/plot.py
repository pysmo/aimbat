"""Create plots for seismograms and ICCS results.

Available plots:

- **seismograms**: the input seismograms of a phase sorted by epicentral distance.
- **stack**: the ICCS cross-correlation stack of a phase.
- **matrix**: seismograms displayed as a matrix image.

Most plot commands support `--context` / `--no-context` to toggle extra
waveform context, and `--all` to include deselected seismograms.

`stack` and `matrix` build an ICCS instance to plot from, which writes the
resulting cross-correlation values to the project database (the same
live-quality write every ICCS-consuming command makes) - despite being
read-only from the user's point of view, they do write to the database.

Each command closes its database session before the plot window opens, so
an open plot holds no database connection.
"""

from typing import Annotated
from uuid import UUID

from cyclopts import App

from .common import (
    DebugParameter,
    IccsPlotParameters,
    event_parameter,
    handle_issues,
    phase_parameter,
    resolve_phase_option,
)

app = App(name="plot", help=__doc__, help_format="markdown")


@app.command(name="seismograms")
@handle_issues
def cli_seismogram_plot(
    event_id: Annotated[UUID, event_parameter()],
    *,
    phase: Annotated[str | None, phase_parameter()] = None,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Plot the input seismograms of a phase sorted by epicentral distance.

    Each seismogram is marked with its initial and refined pick for the
    phase, and filtered with the phase's bandpass settings if they are
    applied.
    """
    from sqlmodel import Session

    from aimbat.core import resolve_phase
    from aimbat.db import engine
    from aimbat.plot import plot_seismograms, show_figure

    with Session(engine) as session:
        fig, _axes = plot_seismograms(
            resolve_phase(session, event_id, phase), return_fig=True
        )

    show_figure(fig)


@app.command(name="stack")
@handle_issues
def cli_plot_stack(
    event_id: Annotated[UUID, event_parameter()],
    *,
    phase: Annotated[str | None, phase_parameter()] = None,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    _: DebugParameter = DebugParameter(),
) -> None:
    """Plot the ICCS stack of a phase.

    Building the ICCS instance writes each seismogram's cross-correlation
    value to the project database, so this command writes to the database
    despite being read-only from the user's point of view.
    """
    from aimbat.actions import prepare_iccs
    from aimbat.plot import plot_stack

    plot_stack(
        prepare_iccs(resolve_phase_option(event_id, phase)).iccs,
        iccs_plot_parameters.context,
        all_seismograms=iccs_plot_parameters.all_seismograms,
        return_fig=False,
    )


@app.command(name="matrix")
@handle_issues
def cli_plot_matrix_image(
    event_id: Annotated[UUID, event_parameter()],
    *,
    phase: Annotated[str | None, phase_parameter()] = None,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    _: DebugParameter = DebugParameter(),
) -> None:
    """Plot the ICCS seismograms of a phase as a matrix image.

    The matrix is assembled from individual waveforms, with each row
    representing a different seismogram. Building the ICCS instance writes
    each seismogram's cross-correlation value to the project database, so
    this command writes to the database despite being read-only from the
    user's point of view.
    """
    from aimbat.actions import prepare_iccs
    from aimbat.plot import plot_matrix_image

    plot_matrix_image(
        prepare_iccs(resolve_phase_option(event_id, phase)).iccs,
        iccs_plot_parameters.context,
        all_seismograms=iccs_plot_parameters.all_seismograms,
        return_fig=False,
    )


if __name__ == "__main__":
    app()
