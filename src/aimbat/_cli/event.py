"""View and manage events in the AIMBAT project."""

import uuid
from typing import Annotated

from cyclopts import App
from sqlmodel import Session

from aimbat._types import EventParameter
from aimbat.models import AimbatEvent

from .common import (
    ALL_EVENTS_PARAMETER,
    DebugParameter,
    GlobalParameters,
    JsonDumpParameters,
    TableParameters,
    event_parameter,
    id_parameter,
    simple_exception,
)

__all__ = [
    "cli_event_delete",
    "cli_event_default",
    "cli_event_dump",
    "cli_event_list",
    "cli_event_parameter_get",
    "cli_event_parameter_set",
    "cli_event_parameter_dump",
    "cli_event_parameter_list",
]

app = App(name="event", help=__doc__, help_format="markdown")
parameter = App(
    name="parameter", help="Manage event parameters.", help_format="markdown"
)
app.command(parameter)


@app.command(name="default")
@simple_exception
def cli_event_default(
    new_default_event_id: Annotated[
        uuid.UUID,
        id_parameter(
            AimbatEvent,
            help="Full UUID or unique prefix of event ID to set as default.",
        ),
    ],
    /,
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Select default event for CLI commands.

    Sets an event to be used by default when no explicit event ID is given.
    Avoids having to specify an event ID for every command.
    """
    from aimbat.core import set_default_event
    from aimbat.db import engine

    with Session(engine) as session:
        set_default_event(session, new_default_event_id)


@app.command(name="delete")
@simple_exception
def cli_event_delete(
    event_id: Annotated[uuid.UUID | None, event_parameter()] = None,
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Delete existing event."""
    from aimbat.core import delete_event, resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        delete_event(session, event.id)


@app.command(name="dump")
@simple_exception
def cli_event_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump the contents of the AIMBAT event table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from rich import print_json

    from aimbat.core import dump_event_table
    from aimbat.db import engine

    with Session(engine) as session:
        print_json(dump_event_table(session, by_alias=dump_parameters.by_alias))


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

    from aimbat.core import dump_event_table
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.utils import TABLE_STYLING, json_to_table

    if short := table_parameters.short:
        exclude = {"id"}
    else:
        exclude = {"short_id"}

    with Session(engine) as session:
        logger.info("Printing AIMBAT events table.")

        json_to_table(
            data=dump_event_table(
                session, from_read_model=True, by_title=True, exclude=exclude
            ),
            title="AIMBAT Events",
            formatters={"Default": TABLE_STYLING.bool_formatter},
            short=short,
        )


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

    from aimbat.core import resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        value = event.parameters.model_dump(mode="json").get(name)
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
        value: New parameter value.
    """
    from sqlmodel import Session

    from aimbat.core import resolve_event, set_event_parameter
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, global_parameters.event_id)
        set_event_parameter(session, event.id, name, value, validate_iccs=True)


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

    from aimbat.core import dump_event_parameter_table, resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        if all_events:
            print_json(data=dump_event_parameter_table(session, by_alias=True))
        else:
            event = resolve_event(session, global_parameters.event_id)
            print_json(event.parameters.model_dump_json(by_alias=True))


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
    settings, minimum cc) in a table.
    """

    from aimbat.core import dump_event_parameter_table, resolve_event
    from aimbat.db import engine
    from aimbat.utils import TABLE_STYLING, json_to_table, uuid_shortener

    short = table_parameters.short

    with Session(engine) as session:
        if all_events:
            title = "Event parameters for all events"
            data = dump_event_parameter_table(session, by_title=True)
        else:
            event = resolve_event(session, global_parameters.event_id)
            title = f"Event parameters for event: {uuid_shortener(session, event) if short else str(event.id)}"
            data = dump_event_parameter_table(
                session, event_id=event.id, by_title=True, exclude={"event_id"}
            )

        json_to_table(
            title=title,
            data=data,
            skip_keys=["ID"],
            formatters={
                "Event ID": lambda x: (
                    uuid_shortener(session, AimbatEvent, str_uuid=x)
                    if short
                    else str(x)
                ),
                "Completed": TABLE_STYLING.bool_formatter,
                "Bandpass apply": TABLE_STYLING.bool_formatter,
            },
            column_order=[
                "Event ID",
                "Completed",
                "Window pre",
                "Window post",
                "Ramp width",
                "Bandpass apply",
                "Bandpass f min",
                "Bandpass f max",
                "Min CC",
            ],
            common_column_kwargs={"highlight": True},
            column_kwargs={
                "Event ID": {
                    "justify": "center",
                    "no_wrap": True,
                    "style": TABLE_STYLING.mine,
                },
                "Completed": {"justify": "center"},
                "Bandpass apply": {"justify": "center"},
            },
        )


if __name__ == "__main__":
    app()
