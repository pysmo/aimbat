"""View and manage stations."""

from aimbat.cli.common import GlobalParameters, TableParameters
from typing import Annotated
from cyclopts import App, Parameter
import uuid


def _delete_station(
    db_url: str | None,
    station_id: uuid.UUID | str,
) -> None:
    from aimbat.lib.station import delete_station_by_id
    from aimbat.lib.common import engine_from_url, string_to_uuid
    from aimbat.lib.models import AimbatStation
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        if not isinstance(station_id, uuid.UUID):
            station_id = string_to_uuid(session, station_id, AimbatStation)
        delete_station_by_id(session, station_id)


def _print_station_table(db_url: str | None, format: bool, all_events: bool) -> None:
    from aimbat.lib.station import print_station_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_station_table(session, format, all_events)


app = App(name="station", help=__doc__, help_format="markdown")


@app.command(name="delete")
def cli_station_delete(
    station_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Delete existing station.

    Parameters:
        station_id: Station ID.
    """

    global_parameters = global_parameters or GlobalParameters()

    _delete_station(
        db_url=global_parameters.db_url,
        station_id=station_id,
    )


@app.command(name="list")
def cli_station_list(
    *,
    all_events: Annotated[bool, Parameter(name="all")] = False,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print information on the stations used in the active event.

    Parameters:
        all_events: Select stations for all events.
    """

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    _print_station_table(global_parameters.db_url, table_parameters.format, all_events)


if __name__ == "__main__":
    app()
