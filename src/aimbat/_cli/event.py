"""View and manage events in the AIMBAT project."""

import uuid
from typing import Annotated, Literal

from cyclopts import App
from sqlmodel import Session

from aimbat._types import EventParameter
from aimbat.models import AimbatEvent

from .common import (
    DebugParameter,
    EventDebugParameters,
    JsonDumpParameters,
    TableParameters,
    event_parameter,
    event_parameter_is_all,
    event_parameter_with_all,
    simple_exception,
)

__all__ = [
    "cli_event_delete",
    "cli_event_dump",
    "cli_event_list",
    "cli_event_parameter_get",
    "cli_event_parameter_set",
    "cli_event_parameter_dump",
    "cli_event_parameter_list",
]

app = App(name="event", help=__doc__, help_format="markdown")
_parameter = App(
    name="parameter", help="Manage event parameters.", help_format="markdown"
)
app.command(_parameter)


@app.command(name="delete")
@simple_exception
def cli_event_delete(
    event_id: Annotated[uuid.UUID, event_parameter()],
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
) -> None:
    """Print a table of events stored in the AIMBAT project."""

    from aimbat.core import dump_event_table
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.models import AimbatEventRead

    from .common import json_to_table

    if raw := table_parameters.raw:
        exclude = {"short_id"}
    else:
        exclude = {"id"}

    with Session(engine) as session:
        logger.info("Printing AIMBAT events table.")

        json_to_table(
            data=dump_event_table(
                session, from_read_model=True, by_title=False, exclude=exclude
            ),
            model=AimbatEventRead,
            title="AIMBAT Events",
            raw=raw,
        )


@_parameter.command(name="get")
@simple_exception
def cli_event_parameter_get(
    name: EventParameter, *, event_debug_parameters: EventDebugParameters
) -> None:
    """Get parameter value for an event.

    Args:
        name: Event parameter name.
    """

    from sqlmodel import Session

    from aimbat.core import resolve_event
    from aimbat.db import engine

    event_id = event_debug_parameters.event_id

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        value = event.parameters.model_dump(mode="json").get(name)
        print(value)


@_parameter.command(name="set")
@simple_exception
def cli_event_parameter_set(
    name: EventParameter, value: str, *, event_debug_parameters: EventDebugParameters
) -> None:
    """Set parameter value for an event.

    Args:
        name: Event parameter name.
        value: New parameter value.
    """
    from sqlmodel import Session

    from aimbat.core import resolve_event, set_event_parameter
    from aimbat.db import engine

    event_id = event_debug_parameters.event_id

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        set_event_parameter(session, event.id, name, value, validate_iccs=True)


@_parameter.command(name="dump")
@simple_exception
def cli_event_parameter_dump(
    *,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Dump event parameter table to json."""
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_event_parameter_table
    from aimbat.db import engine

    by_alias = dump_parameters.by_alias

    with Session(engine) as session:
        print_json(data=dump_event_parameter_table(session, by_alias=by_alias))


@_parameter.command(name="list")
@simple_exception
def cli_event_parameter_list(
    event_id: Annotated[uuid.UUID | Literal["all"], event_parameter_with_all()],
    *,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """List processing parameter for an event or all events.

    Displays all event-level parameters (e.g. time window, bandpass filter
    settings, minimum cc) in a table.
    """

    from aimbat.core import dump_event_parameter_table, resolve_event
    from aimbat.db import engine
    from aimbat.models import AimbatEventParameters, RichColSpec
    from aimbat.utils import uuid_shortener

    from .common import json_to_table

    raw = table_parameters.raw

    with Session(engine) as session:
        if event_parameter_is_all(event_id):
            title = "Event parameters for all events"
            data = dump_event_parameter_table(session)
        else:
            event = resolve_event(session, event_id)
            title = f"Event parameters for event: {uuid_shortener(session, event) if not raw else str(event.id)}"
            data = dump_event_parameter_table(
                session, event_id=event.id, exclude={"event_id"}
            )

        column_order = ["id"]
        col_specs = {
            "id": RichColSpec(
                formatter=lambda x: uuid_shortener(
                    session, AimbatEventParameters, str_uuid=x
                )
            ),
            "event_id": RichColSpec(
                formatter=lambda x: uuid_shortener(session, AimbatEvent, str_uuid=x)
            ),
        }

        json_to_table(
            model=AimbatEventParameters,
            title=title,
            data=data,
            raw=raw,
            col_specs=col_specs,
            column_order=column_order,
        )


if __name__ == "__main__":
    app()
