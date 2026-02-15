"""View and manage seismograms in the AIMBAT project."""

from aimbat.cli.common import GlobalParameters, TableParameters, simple_exception
from aimbat.lib.typing import SeismogramParameter
from typing import Annotated
from cyclopts import App, Parameter
import uuid


@simple_exception
def _delete_seismogram(seismogram_id: uuid.UUID | str) -> None:
    from aimbat.lib.common import string_to_uuid
    from aimbat.lib.db import engine
    from aimbat.lib.models import AimbatSeismogram
    from aimbat.lib.seismogram import delete_seismogram_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        if not isinstance(seismogram_id, uuid.UUID):
            seismogram_id = string_to_uuid(session, seismogram_id, AimbatSeismogram)
        delete_seismogram_by_id(session, seismogram_id)


@simple_exception
def _get_seismogram_parameter(
    seismogram_id: uuid.UUID | str, name: SeismogramParameter
) -> None:
    from aimbat.lib.common import string_to_uuid
    from aimbat.lib.db import engine
    from aimbat.lib.models import AimbatSeismogram
    from aimbat.lib.seismogram import get_seismogram_parameter_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        if not isinstance(seismogram_id, uuid.UUID):
            seismogram_id = string_to_uuid(session, seismogram_id, AimbatSeismogram)
        print(get_seismogram_parameter_by_id(session, seismogram_id, name))


@simple_exception
def _set_seismogram_parameter(
    seismogram_id: uuid.UUID | str,
    name: SeismogramParameter,
    value: str,
) -> None:
    from aimbat.lib.common import string_to_uuid
    from aimbat.lib.db import engine
    from aimbat.lib.models import AimbatSeismogram
    from aimbat.lib.seismogram import set_seismogram_parameter_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        if not isinstance(seismogram_id, uuid.UUID):
            seismogram_id = string_to_uuid(session, seismogram_id, AimbatSeismogram)
        set_seismogram_parameter_by_id(session, seismogram_id, name, value)


@simple_exception
def _print_seismogram_table(short: bool, all_events: bool) -> None:
    from aimbat.lib.seismogram import print_seismogram_table

    print_seismogram_table(short, all_events)


@simple_exception
def _dump_seismogram_table() -> None:
    from aimbat.lib.seismogram import dump_seismogram_table

    dump_seismogram_table()


@simple_exception
def _plot_seismograms(use_qt: bool) -> None:
    from aimbat.lib.seismogram import plot_seismograms
    import pyqtgraph as pg  # type: ignore

    if use_qt:
        pg.mkQApp()

    plot_seismograms(use_qt)

    if use_qt:
        pg.exec()


app = App(name="seismogram", help=__doc__, help_format="markdown")


@app.command(name="delete")
def cli_seismogram_delete(
    seismogram_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Delete existing seismogram.

    Parameters:
        seismogram_id: Seismogram ID.
    """

    global_parameters = global_parameters or GlobalParameters()

    _delete_seismogram(
        seismogram_id=seismogram_id,
    )


@app.command(name="get")
def cli_seismogram_get(
    seismogram_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    name: SeismogramParameter,
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Get the value of a processing parameter.

    Parameters:
        seismogram_id: Seismogram ID number.
        name: Name of the seismogram parameter.
    """

    global_parameters = global_parameters or GlobalParameters()

    _get_seismogram_parameter(
        seismogram_id=seismogram_id,
        name=name,
    )


@app.command(name="set")
def cli_seismogram_set(
    seismogram_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    name: SeismogramParameter,
    value: str,
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Set value of a processing parameter.

    Parameters:
        seismogram_id: Seismogram ID number.
        name: Name of the seismogram parameter.
        value: Value of the seismogram parameter.
    """

    global_parameters = global_parameters or GlobalParameters()

    _set_seismogram_parameter(
        seismogram_id=seismogram_id,
        name=name,
        value=value,
    )


@app.command(name="list")
def cli_seismogram_list(
    *,
    all_events: Annotated[bool, Parameter("all")] = False,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print information on the seismograms in the active event.

    Parameters:
        all_events: Select seismograms for all events."""

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    _print_seismogram_table(table_parameters.short, all_events)


@app.command(name="dump")
def cli_seismogram_dump(
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Dump the contents of the AIMBAT seismogram table to json."""

    global_parameters = global_parameters or GlobalParameters()

    _dump_seismogram_table()


@app.command(name="plot")
def cli_seismogram_plot(*, global_parameters: GlobalParameters | None = None) -> None:
    """Plot seismograms for the active event."""

    global_parameters = global_parameters or GlobalParameters()

    _plot_seismograms(global_parameters.use_qt)


if __name__ == "__main__":
    app()
