"""ICCS processing tools.

Launches various processing tools related to ICCS.
"""

from aimbat.cli.common import CommonParameters
from cyclopts import App


def _plot_stack(db_url: str | None, padded: bool) -> None:
    from aimbat.lib.iccs import plot_stack
    from aimbat.lib.iccs import create_iccs_instance
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        plot_stack(iccs, padded)


def _run_iccs(
    db_url: str | None, autoflip: bool = False, autoselect: bool = False
) -> None:
    from aimbat.lib.iccs import create_iccs_instance, run_iccs
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        run_iccs(session, iccs, autoflip, autoselect)


def _stack_pick(db_url: str | None, padded: bool) -> None:
    from aimbat.lib.iccs import create_iccs_instance, stack_pick
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        stack_pick(session, iccs, padded)


def _stack_timewindow(db_url: str | None, padded: bool) -> None:
    from aimbat.lib.iccs import create_iccs_instance, stack_timewindow
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        iccs = create_iccs_instance(session)
        stack_timewindow(session, iccs, padded)


app = App(name="iccs", help=__doc__, help_format="markdown")


@app.command(name="stack")
def cli_iccs_plot_stack(
    *, pad: bool = True, common: CommonParameters | None = None
) -> None:
    """Plot the ICCS stack of the active event.

    Parameters:
        pad: Add extra padding to the time window for plotting.
    """

    common = common or CommonParameters()

    _plot_stack(common.db_url, pad)


@app.command(name="run")
def cli_iccs_run(
    *,
    autoflip: bool = False,
    autoselect: bool = False,
    common: CommonParameters | None = None,
) -> None:
    """Run the ICCS algorithm.

    Parameters:
        autoflip: Whether to automatically flip seismograms (multiply data by -1).
        autoselect: Whether to automatically de-select seismograms.
    """

    common = common or CommonParameters()

    _run_iccs(common.db_url, autoflip, autoselect)


@app.command(name="pick")
def cli_iccs_stack_pick(
    *, pad: bool = True, common: CommonParameters | None = None
) -> None:
    """Pick a new arrival time in stack.

    Parameters:
        pad: Add extra padding to the time window for plotting.
    """

    common = common or CommonParameters()

    _stack_pick(common.db_url, pad)


@app.command(name="timewindow")
def cli_iccs_stack_timewindow(
    *, pad: bool = True, common: CommonParameters | None = None
) -> None:
    """Pick a new time window in stack.

    Parameters:
        pad: Add extra padding to the time window for plotting.
    """

    common = common or CommonParameters()

    _stack_timewindow(common.db_url, pad)


if __name__ == "__main__":
    app()
