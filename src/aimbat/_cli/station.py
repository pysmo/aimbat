"""View and manage stations."""

from .common import (
    GlobalParameters,
    TableParameters,
    simple_exception,
    id_parameter,
    ALL_EVENTS_PARAMETER,
)
from aimbat.models import AimbatStation
from typing import Annotated
from cyclopts import App
import uuid

app = App(name="station", help=__doc__, help_format="markdown")


@app.command(name="delete")
@simple_exception
def cli_station_delete(
    station_id: Annotated[uuid.UUID, id_parameter(AimbatStation)],
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Delete existing station."""
    from aimbat.db import engine
    from aimbat.core import delete_station_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        delete_station_by_id(session, station_id)


@app.command(name="list")
@simple_exception
def cli_station_list(
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print information on the stations used in the active event."""
    from aimbat.db import engine
    from aimbat.core import print_station_table
    from sqlmodel import Session

    with Session(engine) as session:
        print_station_table(session, table_parameters.short, all_events)


@app.command(name="dump")
@simple_exception
def cli_station_dump(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump the contents of the AIMBAT station table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """

    from aimbat.db import engine
    from aimbat.core import dump_station_table_to_json
    from sqlmodel import Session
    from rich import print_json

    with Session(engine) as session:
        print_json(dump_station_table_to_json(session))


if __name__ == "__main__":
    app()
