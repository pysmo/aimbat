"""View and manage seismograms in the AIMBAT project."""

from aimbat.cli.common import GlobalParameters, TableParameters, simple_exception
from aimbat.aimbat_types import SeismogramParameter
from typing import Annotated
from cyclopts import App, Parameter
import uuid

app = App(name="seismogram", help=__doc__, help_format="markdown")


@app.command(name="delete")
@simple_exception
def cli_seismogram_delete(
    seismogram_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Delete existing seismogram.

    Args:
        seismogram_id: Seismogram ID.
    """
    from aimbat.utils import string_to_uuid
    from aimbat.db import engine
    from aimbat.models import AimbatSeismogram
    from aimbat.core import delete_seismogram_by_id
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        if not isinstance(seismogram_id, uuid.UUID):
            seismogram_id = string_to_uuid(session, seismogram_id, AimbatSeismogram)
        delete_seismogram_by_id(session, seismogram_id)


@app.command(name="get")
@simple_exception
def cli_seismogram_get(
    seismogram_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    name: SeismogramParameter,
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Get the value of a processing parameter.

    Args:
        seismogram_id: Seismogram ID number.
        name: Name of the seismogram parameter.
    """
    from aimbat.utils import string_to_uuid
    from aimbat.db import engine
    from aimbat.models import AimbatSeismogram
    from aimbat.core import get_seismogram_parameter_by_id
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        if not isinstance(seismogram_id, uuid.UUID):
            seismogram_id = string_to_uuid(session, seismogram_id, AimbatSeismogram)
        print(get_seismogram_parameter_by_id(session, seismogram_id, name))


@app.command(name="set")
@simple_exception
def cli_seismogram_set(
    seismogram_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    name: SeismogramParameter,
    value: str,
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Set value of a processing parameter.

    Args:
        seismogram_id: Seismogram ID number.
        name: Name of the seismogram parameter.
        value: Value of the seismogram parameter.
    """
    from aimbat.utils import string_to_uuid
    from aimbat.db import engine
    from aimbat.models import AimbatSeismogram
    from aimbat.core import set_seismogram_parameter_by_id
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        if not isinstance(seismogram_id, uuid.UUID):
            seismogram_id = string_to_uuid(session, seismogram_id, AimbatSeismogram)
        set_seismogram_parameter_by_id(session, seismogram_id, name, value)


@app.command(name="list")
@simple_exception
def cli_seismogram_list(
    *,
    all_events: Annotated[bool, Parameter("all")] = False,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print information on the seismograms in the active event.

    Args:
        all_events: Select seismograms for all events.
    """
    from aimbat.db import engine
    from aimbat.core import print_seismogram_table
    from sqlmodel import Session

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_seismogram_table(session, table_parameters.short, all_events)


@app.command(name="dump")
@simple_exception
def cli_seismogram_dump(
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Dump the contents of the AIMBAT seismogram table to json."""
    from aimbat.db import engine
    from aimbat.core import dump_seismogram_table
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        dump_seismogram_table(session)


@app.command(name="plot")
@simple_exception
def cli_seismogram_plot(*, global_parameters: GlobalParameters | None = None) -> None:
    """Plot seismograms for the active event."""
    from aimbat.db import engine
    from aimbat.core import plot_all_seismograms
    from sqlmodel import Session
    import pyqtgraph as pg  # type: ignore

    global_parameters = global_parameters or GlobalParameters()

    use_qt = global_parameters.use_qt

    if use_qt:
        pg.mkQApp()

    with Session(engine) as session:
        plot_all_seismograms(session, use_qt)

    if use_qt:
        pg.exec()


if __name__ == "__main__":
    app()
