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
    from aimbat.core import print_event_table

    with Session(engine) as session:
        print_event_table(session, table_parameters.short)


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
    from aimbat.core import get_event_parameter
    from sqlmodel import Session

    with Session(engine) as session:
        value = get_event_parameter(session, name)
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
    from aimbat.core import set_event_parameter
    from sqlmodel import Session

    _TIMEDELTA_PARAMS = (EventParameter.WINDOW_PRE, EventParameter.WINDOW_POST)
    parsed_value: Timedelta | str = value
    if name in _TIMEDELTA_PARAMS:
        try:
            parsed_value = Timedelta(seconds=float(value))
        except ValueError:
            parsed_value = Timedelta(value)

    with Session(engine) as session:
        set_event_parameter(session, name, parsed_value)


@parameter.command(name="dump")
@simple_exception
def cli_event_parameter_dump(
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump event parameter table to json."""
    from aimbat.db import engine
    from aimbat.core import dump_event_parameter_table_to_json
    from sqlmodel import Session
    from rich import print_json

    with Session(engine) as session:
        print_json(
            dump_event_parameter_table_to_json(session, all_events, as_string=True)
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
    from aimbat.core import print_event_parameter_table
    from sqlmodel import Session

    with Session(engine) as session:
        print_event_parameter_table(session, table_parameters.short, all_events)


if __name__ == "__main__":
    app()
