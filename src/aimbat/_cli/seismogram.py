"""View and manage seismograms in the AIMBAT project."""

from .common import (
    GlobalParameters,
    TableParameters,
    simple_exception,
    id_parameter,
    ALL_EVENTS_PARAMETER,
)
from aimbat.models import AimbatSeismogram
from aimbat._types import SeismogramParameter
from typing import Annotated
from cyclopts import App
import uuid

app = App(name="seismogram", help=__doc__, help_format="markdown")
parameter = App(
    name="parameter", help="Manage seismogram parameters.", help_format="markdown"
)
app.command(parameter)


@app.command(name="delete")
@simple_exception
def cli_seismogram_delete(
    seismogram_id: Annotated[uuid.UUID, id_parameter(AimbatSeismogram)],
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Delete existing seismogram."""
    from aimbat.db import engine
    from aimbat.core import delete_seismogram_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        delete_seismogram_by_id(session, seismogram_id)


@app.command(name="dump")
@simple_exception
def cli_seismogram_dump(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump the contents of the AIMBAT seismogram table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.db import engine
    from aimbat.core import dump_seismogram_table_to_json
    from sqlmodel import Session
    from rich import print_json

    with Session(engine) as session:
        print_json(dump_seismogram_table_to_json(session))


@app.command(name="list")
@simple_exception
def cli_seismogram_list(
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print information on the seismograms in the active event."""
    from aimbat.db import engine
    from aimbat.core import print_seismogram_table
    from sqlmodel import Session

    with Session(engine) as session:
        print_seismogram_table(session, table_parameters.short, all_events)


@parameter.command(name="get")
@simple_exception
def cli_seismogram_parameter_get(
    seismogram_id: Annotated[uuid.UUID, id_parameter(AimbatSeismogram)],
    name: SeismogramParameter,
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Get the value of a processing parameter.

    Args:
        name: Name of the seismogram parameter.
    """
    from aimbat.db import engine
    from aimbat.core import get_seismogram_parameter_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        print(get_seismogram_parameter_by_id(session, seismogram_id, name))


@parameter.command(name="set")
@simple_exception
def cli_seismogram_parameter_set(
    seismogram_id: Annotated[uuid.UUID, id_parameter(AimbatSeismogram)],
    name: SeismogramParameter,
    value: str,
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Set value of a processing parameter.

    Args:
        name: Name of the seismogram parameter.
        value: Value of the seismogram parameter.
    """
    from aimbat.db import engine
    from aimbat.core import set_seismogram_parameter_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        set_seismogram_parameter_by_id(session, seismogram_id, name, value)


@parameter.command(name="reset")
@simple_exception
def cli_seismogram_parameter_reset(
    seismogram_id: Annotated[uuid.UUID, id_parameter(AimbatSeismogram)],
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Reset all processing parameters to their default values."""
    from aimbat.db import engine
    from aimbat.core import reset_seismogram_parameters_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        reset_seismogram_parameters_by_id(session, seismogram_id)


@parameter.command(name="dump")
@simple_exception
def cli_seismogram_parameter_dump(
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump seismogram parameter table to json."""
    from aimbat.db import engine
    from aimbat.core import dump_seismogram_parameter_table_to_json
    from sqlmodel import Session
    from rich import print_json

    with Session(engine) as session:
        print_json(
            dump_seismogram_parameter_table_to_json(session, all_events, as_string=True)
        )


@parameter.command(name="list")
@simple_exception
def cli_seismogram_parameter_list(
    global_parameters: GlobalParameters = GlobalParameters(),
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """List processing parameter values for seismograms in the active event.

    Displays per-seismogram parameters (e.g. `select`, `flip`, `t1` pick)
    in a table. Use `seismogram parameter set` to modify individual values.
    """

    from aimbat.db import engine
    from aimbat.core import print_seismogram_parameter_table
    from sqlmodel import Session

    with Session(engine) as session:
        print_seismogram_parameter_table(session, table_parameters.short)


if __name__ == "__main__":
    app()
