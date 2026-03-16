"""View and manage stations."""

import uuid
from typing import Annotated

from cyclopts import App

from aimbat.models import AimbatStation

from .common import (
    ALL_EVENTS_PARAMETER,
    DebugParameter,
    GlobalParameters,
    JsonDumpParameters,
    TableParameters,
    id_parameter,
    simple_exception,
)

app = App(name="station", help=__doc__, help_format="markdown")


@app.command(name="delete")
@simple_exception
def cli_station_delete(
    station_id: Annotated[uuid.UUID, id_parameter(AimbatStation)],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Delete existing station."""
    from sqlmodel import Session

    from aimbat.core import delete_station
    from aimbat.db import engine

    with Session(engine) as session:
        delete_station(session, station_id)


@app.command(name="plotseis")
@simple_exception
def cli_station_seismograms_plot(
    station_id: Annotated[uuid.UUID, id_parameter(AimbatStation)],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Plot input seismograms for events recorded at this station."""
    from sqlmodel import Session

    from aimbat.db import engine
    from aimbat.models import AimbatStation
    from aimbat.plot import plot_seismograms

    with Session(engine) as session:
        station = session.get(AimbatStation, station_id)
        if station is None:
            raise ValueError(f"Station with ID {station_id} not found.")
        plot_seismograms(session, station, return_fig=False)


@app.command(name="dump")
@simple_exception
def cli_station_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump the contents of the AIMBAT station table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """

    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_station_table
    from aimbat.db import engine

    with Session(engine) as session:
        print_json(data=dump_station_table(session, by_alias=dump_parameters.by_alias))


@app.command(name="list")
@simple_exception
def cli_station_list(
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print information on the stations used in an event."""
    from sqlmodel import Session

    from aimbat.core import dump_station_table, resolve_event
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.utils import json_to_table, uuid_shortener

    if short := table_parameters.short:
        exclude = {"id"}
    else:
        exclude = {"short_id"}

    with Session(engine) as session:
        if all_events:
            logger.debug("Selecting all AIMBAT stations.")
            data = dump_station_table(
                session, from_read_model=True, by_title=True, exclude=exclude
            )
            title = "AIMBAT stations for all events"
        else:
            logger.debug("Selecting AIMBAT stations used by event.")
            event = resolve_event(session, global_parameters.event_id)
            data = dump_station_table(
                session,
                event_id=event.id,
                from_read_model=True,
                by_title=True,
                exclude={"seismogram_count", "event_count"} | exclude,
            )
            if short:
                title = f"AIMBAT stations for event {event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_shortener(session, event)})"
            else:
                title = f"AIMBAT stations for event {event.time} (ID={event.id})"

        json_to_table(data, title=title, short=short)


if __name__ == "__main__":
    app()
