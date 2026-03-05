"""View and manage events in the AIMBAT project."""

from .common import (
    GlobalParameters,
    TableParameters,
    simple_exception,
    id_parameter,
    ALL_EVENTS_PARAMETER,
)
from aimbat.models import AimbatEvent
from aimbat._types import EventParameter
from typing import Annotated
from pandas import Timedelta
from cyclopts import App
from sqlmodel import Session
import uuid

app = App(name="event", help=__doc__, help_format="markdown")
parameter = App(
    name="parameter", help="Manage event parameters.", help_format="markdown"
)
app.command(parameter)


@app.command(name="delete")
@simple_exception
def cli_event_delete(
    event_id: Annotated[uuid.UUID, id_parameter(AimbatEvent)],
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Delete existing event."""
    from aimbat.db import engine
    from aimbat.core import delete_event_by_id

    with Session(engine) as session:
        delete_event_by_id(session, event_id)


@app.command(name="activate")
@simple_exception
def cli_event_activate(
    event_id: Annotated[uuid.UUID, id_parameter(AimbatEvent)],
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Select the event to be active for processing."""
    from aimbat.core import set_active_event_by_id
    from aimbat.db import engine

    with Session(engine) as session:
        set_active_event_by_id(session, event_id)


@parameter.command(name="get")
@simple_exception
def cli_event_parameter_get(
    name: EventParameter,
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Get parameter value for the active event.

    Args:
        name: Event parameter name.
    """

    from aimbat.db import engine
    from aimbat.core import get_event_parameter, get_active_event
    from sqlmodel import Session

    with Session(engine) as session:
        active_event = get_active_event(session)
        value = get_event_parameter(session, active_event, name)
        if isinstance(value, Timedelta):
            print(f"{value.total_seconds()}s")
        else:
            print(value)


@parameter.command(name="set")
@simple_exception
def cli_event_parameter_set(
    name: EventParameter,
    value: str,
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Set parameter value for the active event.

    Args:
        name: Event parameter name.
        value: Event parameter value. For timedelta parameters, bare numbers
            are interpreted as seconds.
    """
    from aimbat.db import engine
    from aimbat.core import set_event_parameter, get_active_event
    from sqlmodel import Session

    _TIMEDELTA_PARAMS = (EventParameter.WINDOW_PRE, EventParameter.WINDOW_POST)
    parsed_value: Timedelta | str = value
    if name in _TIMEDELTA_PARAMS:
        try:
            parsed_value = Timedelta(seconds=float(value))
        except ValueError:
            parsed_value = Timedelta(value)

    with Session(engine) as session:
        active_event = get_active_event(session)
        set_event_parameter(session, active_event, name, parsed_value)


@parameter.command(name="dump")
@simple_exception
def cli_event_parameter_dump(
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump event parameter table to json."""
    from aimbat.db import engine
    from aimbat.core import dump_event_parameter_table_to_json, get_active_event
    from sqlmodel import Session
    from rich import print_json

    with Session(engine) as session:
        active_event = get_active_event(session) if not all_events else None
        print_json(
            dump_event_parameter_table_to_json(
                session, all_events, as_string=True, event=active_event
            )
        )


@app.command(name="dump")
@simple_exception
def cli_event_dump(
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump the contents of the AIMBAT event table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.db import engine
    from aimbat.core import dump_event_table_to_json
    from rich import print_json

    with Session(engine) as session:
        print_json(dump_event_table_to_json(session))


@app.command(name="list")
@simple_exception
def cli_event_list(
    *,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print a table of events stored in the AIMBAT project.

    The active event is highlighted. Use `event activate` to change which event
    is processed by subsequent commands.
    """
    from aimbat.db import engine
    from aimbat.core import dump_event_table_to_json
    from aimbat.utils import uuid_shortener, json_to_table, TABLE_STYLING
    from aimbat.logger import logger
    from pandas import Timestamp

    short = table_parameters.short

    with Session(engine) as session:
        logger.info("Printing AIMBAT events table.")

        json_to_table(
            data=dump_event_table_to_json(session, as_string=False),
            title="AIMBAT Events",
            column_order=[
                "id",
                "active",
                "time",
                "latitude",
                "longitude",
                "depth",
                "completed",
                "seismogram_count",
                "station_count",
            ],
            formatters={
                "id": lambda x: (
                    uuid_shortener(session, AimbatEvent, str_uuid=x) if short else x
                ),
                "active": TABLE_STYLING.bool_formatter,
                "time": lambda x: TABLE_STYLING.timestamp_formatter(
                    Timestamp(x), short
                ),
                "latitude": lambda x: f"{x:.3f}" if short else str(x),
                "longitude": lambda x: f"{x:.3f}" if short else str(x),
                "depth": lambda x: f"{x:.0f}" if short and x is not None else str(x),
                "completed": TABLE_STYLING.bool_formatter,
                "last_modified": lambda x: TABLE_STYLING.timestamp_formatter(
                    Timestamp(x), short
                ),
            },
            common_column_kwargs={"justify": "center"},
            column_kwargs={
                "id": {
                    "header": "ID (shortened)" if short else "ID",
                    "style": TABLE_STYLING.id,
                    "no_wrap": True,
                },
                "active": {"style": TABLE_STYLING.mine, "no_wrap": True},
                "time": {
                    "header": "Date & Time",
                    "style": TABLE_STYLING.mine,
                    "no_wrap": True,
                },
                "last_modified": {
                    "header": "Last Modified",
                    "style": TABLE_STYLING.mine,
                    "no_wrap": True,
                },
                "latitude": {"style": TABLE_STYLING.mine},
                "longitude": {"style": TABLE_STYLING.mine},
                "depth": {"style": TABLE_STYLING.mine},
                "completed": {"style": TABLE_STYLING.parameters},
                "seismogram_count": {
                    "header": "# Seismograms",
                    "style": TABLE_STYLING.linked,
                },
                "station_count": {
                    "header": "# Stations",
                    "style": TABLE_STYLING.linked,
                },
            },
        )


@parameter.command(name="list")
@simple_exception
def cli_event_parameter_list(
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """List processing parameter values for the active event.

    Displays all event-level parameters (e.g. time window, bandpass filter
    settings, minimum ccnorm) in a table.
    """

    from aimbat.db import engine
    from aimbat.core import dump_event_parameter_table_to_json, get_active_event
    from aimbat.utils import uuid_shortener, json_to_table, TABLE_STYLING
    from aimbat.logger import logger

    short = table_parameters.short

    with Session(engine) as session:
        if all_events:
            logger.info("Printing AIMBAT event parameters table for all events.")
            json_to_table(
                data=dump_event_parameter_table_to_json(
                    session, all_events=True, as_string=False
                ),
                title="Event parameters for all events",
                skip_keys=["id"],
                column_order=[
                    "event_id",
                    "completed",
                    "window_pre",
                    "window_post",
                    "min_ccnorm",
                ],
                formatters={
                    "event_id": lambda x: (
                        uuid_shortener(session, AimbatEvent, str_uuid=x) if short else x
                    ),
                },
                common_column_kwargs={"highlight": True},
                column_kwargs={
                    "event_id": {
                        "header": "Event ID (shortened)" if short else "Event ID",
                        "justify": "center",
                        "style": TABLE_STYLING.mine,
                    },
                },
            )
        else:
            logger.info("Printing AIMBAT event parameters table for active event.")

            active_event = get_active_event(session)
            json_to_table(
                data=active_event.parameters.model_dump(mode="json"),
                title=f"Event parameters for event: {uuid_shortener(session, active_event) if short else str(active_event.id)}",
                skip_keys=["id", "event_id"],
                common_column_kwargs={"highlight": True},
                column_kwargs={
                    "Key": {
                        "header": "Parameter",
                        "justify": "left",
                        "style": TABLE_STYLING.id,
                    },
                },
            )


if __name__ == "__main__":
    app()
