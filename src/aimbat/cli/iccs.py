"""ICCS processing tools.

Launches various processing tools related to ICCS.
"""

from typing import Annotated
from aimbat.cli.common import GlobalParameters, simple_exception
from cyclopts import App, Parameter
from dataclasses import dataclass


@Parameter(name="*")
@dataclass
class IccsPlotParameters:
    context: bool = True
    "Plot seismograms with extra context instead of the short tapered ones used for cross-correlation."
    all: bool = False
    "Include all seismograms in the plot, even if not used in stack."


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
@simple_exception
def cli_iccs_run(
    *,
    autoflip: bool = False,
    autoselect: bool = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Run the ICCS algorithm.

    Args:
        autoflip: Whether to automatically flip seismograms (multiply data by -1).
        autoselect: Whether to automatically de-select seismograms.
    """
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, run_iccs
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        run_iccs(session, iccs, autoflip, autoselect)


@plot.command(name="stack")
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


@plot.command(name="image")
@simple_exception
def cli_iccs_plot_seismograms(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Plot the ICCS seismograms of the active event as an image."""
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, plot_seismograms
    from sqlmodel import Session

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        plot_seismograms(iccs, iccs_parameters.context, iccs_parameters.all)


@update.command(name="pick")
@simple_exception
def cli_iccs_update_pick(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    use_seismogram_image: Annotated[bool, Parameter(name="img")] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new arrival time.

    Args:
        use_seismogram_image: Use the seismogram image to update pick.
    """
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, update_pick
    from sqlmodel import Session

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        update_pick(
            session,
            iccs,
            iccs_parameters.context,
            iccs_parameters.all,
            use_seismogram_image,
        )


@update.command(name="window")
@simple_exception
def cli_iccs_update_timewindow(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    use_seismogram_image: Annotated[bool, Parameter(name="img")] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new time window.

    Args:
        use_seismogram_image: Use the seismogram image to pick the time window.
    """
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, update_timewindow
    from sqlmodel import Session

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        update_timewindow(
            session,
            iccs,
            iccs_parameters.context,
            iccs_parameters.all,
            use_seismogram_image,
        )


@update.command(name="ccnorm")
@simple_exception
def cli_iccs_update_min_ccnorm(
    *,
    iccs_parameters: IccsPlotParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new minimum cross-correlation norm for auto-selection."""
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, update_min_ccnorm
    from sqlmodel import Session

    iccs_parameters = iccs_parameters or IccsPlotParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        iccs = create_iccs_instance(session)
        update_min_ccnorm(session, iccs, iccs_parameters.context, iccs_parameters.all)


if __name__ == "__main__":
    app()
