"""View and manage stations."""

from ._common import GlobalParameters, TableParameters, simple_exception
from typing import Annotated
from cyclopts import App, Parameter
import uuid

app = App(name="station", help=__doc__, help_format="markdown")


@app.command(name="delete")
@simple_exception
def cli_station_delete(
    station_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Delete existing station.

    Args:
        station_id: Station ID.
    """
    from aimbat.db import engine
    from aimbat.utils import string_to_uuid
    from aimbat.core import delete_station_by_id
    from aimbat.models import AimbatStation
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        if not isinstance(station_id, uuid.UUID):
            station_id = string_to_uuid(session, station_id, AimbatStation)
        delete_station_by_id(session, station_id)


@app.command(name="list")
@simple_exception
def cli_station_list(
    *,
    all_events: Annotated[bool, Parameter(name="all")] = False,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print information on the stations used in the active event.

    Args:
        all_events: Select stations for all events.
    """
    from aimbat.db import engine
    from aimbat.core import print_station_table
    from sqlmodel import Session

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_station_table(session, table_parameters.short, all_events)


@app.command(name="dump")
@simple_exception
def cli_station_dump(
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Dump the contents of the AIMBAT station table to json."""

    from aimbat.db import engine
    from aimbat.core import dump_station_table_to_json
    from sqlmodel import Session
    from rich import print_json

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_json(dump_station_table_to_json(session))


if __name__ == "__main__":
    app()
