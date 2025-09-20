"""ICCS processing tools.

Launches various processing tools related to ICCS.
"""

from typing import Annotated
from aimbat.cli.common import GlobalParameters
from cyclopts import App, Parameter


def _plot_stack(db_url: str | None, padded: bool) -> None:
    from aimbat.lib.iccs import create_iccs_instance, plot_stack
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        plot_stack(iccs, padded)


def _plot_seismograms(db_url: str | None, padded: bool) -> None:
    from aimbat.lib.iccs import create_iccs_instance, plot_seismograms
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        plot_seismograms(iccs, padded)


def _run_iccs(
    db_url: str | None, autoflip: bool = False, autoselect: bool = False
) -> None:
    from aimbat.lib.iccs import create_iccs_instance, run_iccs
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        run_iccs(session, iccs, autoflip, autoselect)


def _update_pick(db_url: str | None, padded: bool, use_seismogram_image: bool) -> None:
    from aimbat.lib.iccs import create_iccs_instance, update_pick
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        update_pick(session, iccs, padded, use_seismogram_image)


def _update_timewindow(
    db_url: str | None, padded: bool, use_seismogram_image: bool
) -> None:
    from aimbat.lib.iccs import create_iccs_instance, update_timewindow
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        update_timewindow(session, iccs, padded, use_seismogram_image)


def _update_min_ccnorm(db_url: str | None, padded: bool) -> None:
    from aimbat.lib.iccs import create_iccs_instance, update_min_ccnorm
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        update_min_ccnorm(session, iccs, padded)


app = App(name="iccs", help=__doc__, help_format="markdown")
plot = App(name="plot", help="Plot ICCS data and results.", help_format="markdown")
update = App(
    name="update",
    help="Update parameters controlling the ICCS algorithm.",
    help_format="markdown",
)
app.command(plot)
app.command(update)


@plot.command(name="stack")
def cli_iccs_plot_stack(
    *, pad: bool = True, global_parameters: GlobalParameters | None = None
) -> None:
    """Plot the ICCS stack of the active event.

    Parameters:
        pad: Add extra padding to the time window for plotting.
    """

    global_parameters = global_parameters or GlobalParameters()

    _plot_stack(global_parameters.db_url, pad)


@plot.command(name="seismograms")
def cli_iccs_plot_seismograms(
    *, pad: bool = True, global_parameters: GlobalParameters | None = None
) -> None:
    """Plot the ICCS seismograms of the active event.

    Parameters:
        pad: Add extra padding to the time window for plotting.
    """

    global_parameters = global_parameters or GlobalParameters()

    _plot_seismograms(global_parameters.db_url, pad)


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

    _run_iccs(global_parameters.db_url, autoflip, autoselect)


@update.command(name="pick")
def cli_iccs_update_pick(
    *,
    pad: bool = True,
    use_seismogram_image: Annotated[bool, Parameter(name="img")] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new arrival time.

    Parameters:
        pad: Add extra padding to the time window for plotting.
        use_seismogram_image: Use the seismogram image to update pick.
    """

    global_parameters = global_parameters or GlobalParameters()

    _update_pick(global_parameters.db_url, pad, use_seismogram_image)


@update.command(name="timewindow")
def cli_iccs_update_timewindow(
    *,
    pad: bool = True,
    use_seismogram_image: Annotated[bool, Parameter(name="img")] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Pick a new time window.

    Parameters:
        pad: Add extra padding to the time window for plotting.
        use_seismogram_image: Use the seismogram image to pick the time window.
    """

    global_parameters = global_parameters or GlobalParameters()

    _update_timewindow(global_parameters.db_url, pad, use_seismogram_image)


@update.command(name="ccnorm")
def cli_iccs_update_min_ccnorm(
    *, pad: bool = True, global_parameters: GlobalParameters | None = None
) -> None:
    """Pick a new minimum cross-correlation norm for auto-selection.

    Parameters:
        pad: Add extra padding to the time window for plotting.
    """

    global_parameters = global_parameters or GlobalParameters()

    _update_min_ccnorm(global_parameters.db_url, pad)


if __name__ == "__main__":
    app()
