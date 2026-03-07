"""View and manage stations."""

import uuid
from typing import Annotated

from cyclopts import App

from aimbat.models import AimbatStation

from .common import (
    ALL_EVENTS_PARAMETER,
    GlobalParameters,
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
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Delete existing station."""
    from sqlmodel import Session

    from aimbat.core import delete_station_by_id
    from aimbat.db import engine

    with Session(engine) as session:
        delete_station_by_id(session, station_id)


@app.command(name="dump")
@simple_exception
def cli_station_dump(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump the contents of the AIMBAT station table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """

    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_station_table_to_json
    from aimbat.db import engine

    with Session(engine) as session:
        print_json(dump_station_table_to_json(session))


@app.command(name="list")
@simple_exception
def cli_station_list(
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print information on the stations used in an event."""
    from typing import Any

    from sqlmodel import Session

    from aimbat.core import (
        get_stations_in_event,
        resolve_event,
    )
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.utils import TABLE_STYLING, json_to_table, uuid_shortener

    short = table_parameters.short

    with Session(engine) as session:
        logger.info("Printing station table.")

        title = "AIMBAT stations for all events"

        if all_events:
            logger.debug("Selecting all AIMBAT stations.")
            from aimbat.core import dump_station_table_with_counts

            data = dump_station_table_with_counts(session)
        else:
            logger.debug("Selecting AIMBAT stations used by event.")
            event = resolve_event(session, global_parameters.event_id)
            data = get_stations_in_event(session, event, as_json=True)

            if short:
                title = f"AIMBAT stations for event {event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_shortener(session, event)})"
            else:
                title = f"AIMBAT stations for event {event.time} (ID={event.id})"

        column_order = [
            "id",
            "name",
            "network",
            "channel",
            "location",
            "latitude",
            "longitude",
            "elevation",
        ]
        if all_events:
            column_order.extend(["seismogram_count", "event_count"])

        column_kwargs: dict[str, dict[str, Any]] = {
            "id": {
                "header": "ID (shortened)" if short else "ID",
                "style": TABLE_STYLING.id,
                "justify": "center",
                "no_wrap": True,
            },
            "name": {
                "header": "Name",
                "style": TABLE_STYLING.mine,
                "justify": "center",
                "no_wrap": True,
            },
            "network": {
                "header": "Network",
                "style": TABLE_STYLING.mine,
                "justify": "center",
                "no_wrap": True,
            },
            "channel": {
                "header": "Channel",
                "style": TABLE_STYLING.mine,
                "justify": "center",
            },
            "location": {
                "header": "Location",
                "style": TABLE_STYLING.mine,
                "justify": "center",
            },
            "latitude": {
                "header": "Latitude",
                "style": TABLE_STYLING.mine,
                "justify": "center",
            },
            "longitude": {
                "header": "Longitude",
                "style": TABLE_STYLING.mine,
                "justify": "center",
            },
            "elevation": {
                "header": "Elevation",
                "style": TABLE_STYLING.mine,
                "justify": "center",
            },
            "seismogram_count": {
                "header": "# Seismograms",
                "style": TABLE_STYLING.linked,
                "justify": "center",
            },
            "event_count": {
                "header": "# Events",
                "style": TABLE_STYLING.linked,
                "justify": "center",
            },
        }

        formatters = {
            "id": lambda x: (
                uuid_shortener(session, AimbatStation, str_uuid=x) if short else str(x)
            ),
            "latitude": lambda x: f"{x:.3f}" if short else str(x),
            "longitude": lambda x: f"{x:.3f}" if short else str(x),
            "elevation": lambda x: f"{x:.0f}" if short else str(x),
        }

        json_to_table(
            data,
            title=title,
            column_order=column_order,
            column_kwargs=column_kwargs,
            formatters=formatters,
        )


if __name__ == "__main__":
    app()
