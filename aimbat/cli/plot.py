"""Create AIMBAT plots."""

from aimbat.cli.common import CommonParameters
from cyclopts import App


def _plot_seismograms(db_url: str | None, use_qt: bool = False) -> None:
    from aimbat.lib.plot import plot_seismograms
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session
    import pyqtgraph as pg  # type: ignore

    if use_qt:
        pg.mkQApp()

    with Session(engine_from_url(db_url)) as session:
        plot_seismograms(session, use_qt)

    if use_qt:
        pg.exec()


def _plot_stack(db_url: str | None) -> None:
    from aimbat.lib.plot import plot_stack
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        plot_stack(session)


app = App(name="plot", help=__doc__, help_format="markdown")


@app.command(name="seismograms")
def plot_cli_seismograms(*, common: CommonParameters | None = None) -> None:
    """Plot seismograms for the active event."""

    common = common or CommonParameters()

    _plot_seismograms(common.db_url, common.use_qt)


@app.command(name="stack")
def plot_cli_stack(*, common: CommonParameters | None = None) -> None:
    """Plot the ICCS stack of the active event."""

    common = common or CommonParameters()

    _plot_stack(common.db_url)


if __name__ == "__main__":
    app()
