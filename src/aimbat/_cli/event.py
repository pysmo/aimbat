"""View and manage events in the AIMBAT project."""

import uuid
from typing import Annotated

from cyclopts import App
from pandas import Timedelta
from sqlmodel import Session

from aimbat._types import EventParameter
from aimbat.models import AimbatEvent

from .common import (
    ALL_EVENTS_PARAMETER,
    DebugParameter,
    GlobalParameters,
    TableParameters,
    id_parameter,
    simple_exception,
)

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
    _: DebugParameter = DebugParameter(),
) -> None:
    """Delete existing event."""
    from aimbat.core import delete_event_by_id
    from aimbat.db import engine

    with Session(engine) as session:
        delete_event_by_id(session, event_id)


@app.command(name="default")
@simple_exception
def cli_event_default(
    new_default_event_id: Annotated[uuid.UUID, id_parameter(AimbatEvent)],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Select default event for CLI commands.

    Sets an event to be used by default when no explicit event ID is given.
    Avoids having to specify an event ID for every command.
    """
    from aimbat.core import set_default_event_by_id
    from aimbat.db import engine

    with Session(engine) as session:
        set_default_event_by_id(session, new_default_event_id)


@parameter.command(name="get")
@simple_exception
def cli_event_parameter_get(
    name: EventParameter,
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Get parameter value for an event.

    Args:
        name: Event parameter name.
    """

    from sqlmodel import Session

    from aimbat.core import get_event_parameter, resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        value = get_event_parameter(session, event, name)
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
    """Set parameter value for an event.

    Args:
        name: Event parameter name.
        value: Event parameter value. For timedelta parameters, bare numbers
            are interpreted as seconds.
    """
    from sqlmodel import Session

    from aimbat.core import resolve_event, set_event_parameter
    from aimbat.db import engine

    _TIMEDELTA_PARAMS = (EventParameter.WINDOW_PRE, EventParameter.WINDOW_POST)
    parsed_value: Timedelta | str = value
    if name in _TIMEDELTA_PARAMS:
        try:
            parsed_value = Timedelta(seconds=float(value))
        except ValueError:
            parsed_value = Timedelta(value)

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        set_event_parameter(session, event, name, parsed_value, validate_iccs=True)


@parameter.command(name="dump")
@simple_exception
def cli_event_parameter_dump(
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump event parameter table to json."""
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_event_parameter_table_to_json, resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        event = (
            resolve_event(session, global_parameters.event_id)
            if not all_events
            else None
        )
        print_json(
            dump_event_parameter_table_to_json(
                session, all_events, as_string=True, event=event
            )
        )


@app.command(name="dump")
@simple_exception
def cli_event_dump(*, _: DebugParameter = DebugParameter()) -> None:
    """Dump the contents of the AIMBAT event table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from rich import print_json

    from aimbat.core import dump_event_table_to_json
    from aimbat.db import engine

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

    The default event is highlighted. Use `event default` to change which event
    is processed by subsequent commands.
    """
    from pandas import Timestamp

    from aimbat.core import dump_event_table_to_json
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.utils import TABLE_STYLING, json_to_table, uuid_shortener

    short = table_parameters.short

    with Session(engine) as session:
        logger.info("Printing AIMBAT events table.")

        json_to_table(
            data=dump_event_table_to_json(session, as_string=False),
            title="AIMBAT Events",
            column_order=[
                "id",
                "is_default",
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
                "is_default": TABLE_STYLING.bool_formatter,
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
                "is_default": {
                    "header": "Default",
                    "style": TABLE_STYLING.mine,
                    "no_wrap": True,
                },
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
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """List processing parameter values for the default event.

    Displays all event-level parameters (e.g. time window, bandpass filter
    settings, minimum ccnorm) in a table.
    """

    from aimbat.core import dump_event_parameter_table_to_json, resolve_event
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.utils import TABLE_STYLING, json_to_table, uuid_shortener

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
            logger.info("Printing AIMBAT event parameters table for default event.")

            event = resolve_event(session, global_parameters.event_id)
            json_to_table(
                data=event.parameters.model_dump(mode="json"),
                title=f"Event parameters for event: {uuid_shortener(session, event) if short else str(event.id)}",
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
