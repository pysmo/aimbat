"""ICCS processing tools.

Launches various processing tools related to ICCS.
"""

from typing import Annotated
from aimbat.cli.common import GlobalParameters, IccsPlotParameters
from cyclopts import App, Parameter


def _run_iccs(autoflip: bool = False, autoselect: bool = False) -> None:
    from aimbat.lib.db import engine
    from aimbat.lib.iccs import create_iccs_instance, run_iccs
    from sqlmodel import Session

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        run_iccs(session, iccs, autoflip, autoselect)


def _plot_stack(padded: bool, all: bool) -> None:
    from aimbat.lib.db import engine
    from aimbat.lib.iccs import create_iccs_instance, plot_stack
    from sqlmodel import Session

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        plot_stack(iccs, padded, all)


def _plot_seismograms(padded: bool, all: bool) -> None:
    from aimbat.lib.db import engine
    from aimbat.lib.iccs import create_iccs_instance, plot_seismograms
    from sqlmodel import Session

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        plot_seismograms(iccs, padded, all)


def _update_pick(padded: bool, all: bool, use_seismogram_image: bool) -> None:
    from aimbat.lib.db import engine
    from aimbat.lib.iccs import create_iccs_instance, update_pick
    from sqlmodel import Session

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        update_pick(session, iccs, padded, all, use_seismogram_image)


def _update_timewindow(padded: bool, all: bool, use_seismogram_image: bool) -> None:
    from aimbat.lib.db import engine
    from aimbat.lib.iccs import create_iccs_instance, update_timewindow
    from sqlmodel import Session

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        update_timewindow(session, iccs, padded, all, use_seismogram_image)


def _update_min_ccnorm(padded: bool, all: bool) -> None:
    from aimbat.lib.db import engine
    from aimbat.lib.iccs import create_iccs_instance, update_min_ccnorm
    from sqlmodel import Session

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        update_min_ccnorm(session, iccs, padded, all)


app = App(name="iccs", help=__doc__, help_format="markdown")
plot = App(name="plot", help="Plot ICCS data and results.", help_format="markdown")
update = App(
    name="update",
    help="Update parameters controlling the ICCS algorithm.",
    help_format="markdown",
)
app.command(plot)
app.command(update)


@app.command(name="run")
def cli_iccs_run(
    *,
    autoflip: bool = False,
    autoselect: bool = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Run the ICCS algorithm.

    Parameters:
        autoflip: Whether to automatically flip seismograms (multiply data by -1).
        autoselect: Whether to automatically de-select seismograms.
    """

    global_parameters = global_parameters or GlobalParameters()

    _run_iccs(autoflip, autoselect)


@plot.command(name="stack")
def cli_iccs_plot_stack(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Plot the ICCS stack of the active event."""

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    _plot_stack(iccs_parameters.pad, iccs_parameters.all)


@plot.command(name="image")
def cli_iccs_plot_seismograms(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Plot the ICCS seismograms of the active event as an image.

    Parameters:
        pad: Add extra padding to the time window for plotting.
    """

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    _plot_seismograms(iccs_parameters.pad, iccs_parameters.all)


@update.command(name="pick")
def cli_iccs_update_pick(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    use_seismogram_image: Annotated[bool, Parameter(name="img")] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new arrival time.

    Parameters:
        use_seismogram_image: Use the seismogram image to update pick.
    """

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    _update_pick(
        iccs_parameters.pad,
        iccs_parameters.all,
        use_seismogram_image,
    )


@update.command(name="window")
def cli_iccs_update_timewindow(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    use_seismogram_image: Annotated[bool, Parameter(name="img")] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new time window.

    Parameters:
        use_seismogram_image: Use the seismogram image to pick the time window.
    """

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    _update_timewindow(
        iccs_parameters.pad,
        iccs_parameters.all,
        use_seismogram_image,
    )


@update.command(name="ccnorm")
def cli_iccs_update_min_ccnorm(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new minimum cross-correlation norm for auto-selection."""

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    _update_min_ccnorm(iccs_parameters.pad, iccs_parameters.all)


if __name__ == "__main__":
    app()
