"""View and manage seismograms in the AIMBAT project."""

from aimbat.cli.common import CommonParameters
from aimbat.lib.typing import SeismogramParameter
from typing import Annotated
from cyclopts import App, Parameter


def _get_seismogram_parameter(
    db_url: str | None,
    seismogram_id: int,
    name: SeismogramParameter,
) -> None:
    from aimbat.lib.seismogram import get_seismogram_parameter_by_id
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print(get_seismogram_parameter_by_id(session, seismogram_id, name))


def _set_seismogram_parameter(
    db_url: str | None,
    seismogram_id: int,
    name: SeismogramParameter,
    value: str,
) -> None:
    from aimbat.lib.seismogram import set_seismogram_parameter_by_id
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        set_seismogram_parameter_by_id(session, seismogram_id, name, value)


def _print_seismogram_table(db_url: str | None, all_events: bool) -> None:
    from aimbat.lib.seismogram import print_seismogram_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_seismogram_table(session, all_events)


def _plot_seismograms(db_url: str | None, use_qt: bool = False) -> None:
    from aimbat.lib.seismogram import plot_seismograms
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session
    import pyqtgraph as pg  # type: ignore

    if use_qt:
        pg.mkQApp()

    with Session(engine_from_url(db_url)) as session:
        plot_seismograms(session, use_qt)

    if use_qt:
        pg.exec()


app = App(name="seismogram", help=__doc__, help_format="markdown")


@app.command(name="list")
def cli_seismogram_list(
    *,
    all_events: Annotated[bool, Parameter("all")] = False,
    common: CommonParameters | None = None,
) -> None:
    """Print information on the seismograms in the active event.

    Parameters:
        all_events: Select seismograms for all events."""

    common = common or CommonParameters()

    _print_seismogram_table(common.db_url, all_events)


@app.command(name="plot")
def cli_seismogram_plot(*, common: CommonParameters | None = None) -> None:
    """Plot seismograms for the active event."""

    common = common or CommonParameters()

    _plot_seismograms(common.db_url, common.use_qt)


@app.command(name="get")
def cli_seismogram_get(
    seismogram_id: Annotated[int, Parameter(name="id")],
    name: SeismogramParameter,
    *,
    common: CommonParameters | None = None,
) -> None:
    """Get the value of a processing parameter.

    Parameters:
        seismogram_id: Seismogram ID number.
        name: Name of the seismogram parameter.
    """

    common = common or CommonParameters()

    _get_seismogram_parameter(
        db_url=common.db_url,
        seismogram_id=seismogram_id,
        name=name,
    )


@app.command(name="set")
def cli_seismogram_set(
    seismogram_id: Annotated[int, Parameter(name="id")],
    name: SeismogramParameter,
    value: str,
    *,
    common: CommonParameters | None = None,
) -> None:
    """Set value of a processing parameter.

    Parameters:
        seismogram_id: Seismogram ID number.
        name: Name of the seismogram parameter.
        value: Value of the seismogram parameter.
    """

    common = common or CommonParameters()

    _set_seismogram_parameter(
        db_url=common.db_url,
        seismogram_id=seismogram_id,
        name=name,
        value=value,
    )


if __name__ == "__main__":
    app()
