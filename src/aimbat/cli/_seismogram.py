"""View and manage seismograms in the AIMBAT project."""

from ._common import GlobalParameters, TableParameters, simple_exception
from aimbat.aimbat_types import SeismogramParameter
from typing import Annotated
from cyclopts import App, Parameter
import uuid

app = App(name="seismogram", help=__doc__, help_format="markdown")
parameter = App(
    name="parameter", help="Manage seismogram parameters.", help_format="markdown"
)
app.command(parameter)


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


@app.command(name="dump")
@simple_exception
def cli_seismogram_dump(
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Dump the contents of the AIMBAT seismogram table to json."""
    from aimbat.db import engine
    from aimbat.core import dump_seismogram_table_to_json
    from sqlmodel import Session
    from rich import print_json

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_json(dump_seismogram_table_to_json(session))


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


@parameter.command(name="get")
@simple_exception
def cli_seismogram_parameter_get(
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


@parameter.command(name="set")
@simple_exception
def cli_seismogram_parameter_set(
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


@parameter.command(name="dump")
@simple_exception
def cli_seismogram_parameter_dump(
    all_events: Annotated[
        bool,
        Parameter(
            name="all",
            help="Dump parameters for all events instead of just the active event.",
        ),
    ] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Dump seismogram parameter table to json."""
    from aimbat.db import engine
    from aimbat.core import dump_seismogram_parameter_table_to_json
    from sqlmodel import Session
    from rich import print_json

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_json(
            dump_seismogram_parameter_table_to_json(session, all_events, as_string=True)
        )


@parameter.command(name="list")
@simple_exception
def cli_seismogram_parameter_list(
    global_parameters: GlobalParameters | None = None,
    table_parameters: TableParameters | None = None,
) -> None:
    """List parameter values for the active event."""
    from aimbat.db import engine
    from aimbat.core import print_seismogram_parameter_table
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()
    table_parameters = table_parameters or TableParameters()

    with Session(engine) as session:
        print_seismogram_parameter_table(session, table_parameters.short)


if __name__ == "__main__":
    app()
