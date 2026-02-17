"""View and manage events in the AIMBAT project."""

from aimbat.cli.common import GlobalParameters, TableParameters, simple_exception
from aimbat.lib.typing import EventParameter
from typing import Annotated
from datetime import timedelta
from cyclopts import App, Parameter
from sqlmodel import Session
import uuid


def string_to_event_uuid(session: Session, event_id: str) -> uuid.UUID:
    from aimbat.lib.models import AimbatEvent
    from aimbat.lib.common import string_to_uuid, HINTS

    return string_to_uuid(
        session,
        event_id,
        AimbatEvent,
        custom_error=f"Unable to find event using id: {event_id}. {HINTS.LIST_EVENTS}",
    )


@simple_exception
def _delete_event(event_id: uuid.UUID | str) -> None:
    from aimbat.lib.event import delete_event_by_id
    from aimbat.lib.db import engine

    with Session(engine) as session:
        if not isinstance(event_id, uuid.UUID):
            event_id = string_to_event_uuid(session, event_id)
        delete_event_by_id(session, event_id)


@simple_exception
def _print_event_table(short: bool) -> None:
    from aimbat.lib.event import print_event_table

    print_event_table(short)


@simple_exception
def _set_active_event_by_id(event_id: uuid.UUID | str) -> None:
    from aimbat.lib.event import set_active_event_by_id
    from aimbat.lib.db import engine

    with Session(engine) as session:
        if not isinstance(event_id, uuid.UUID):
            event_id = string_to_event_uuid(session, event_id)
        set_active_event_by_id(session, event_id)


@simple_exception
def _dump_event_table() -> None:
    from aimbat.lib.event import dump_event_table

    dump_event_table()


@simple_exception
def _get_event_parameters(
    name: EventParameter,
) -> None:
    from aimbat.lib.db import engine
    from aimbat.lib.event import get_event_parameter
    from sqlmodel import Session

    with Session(engine) as session:
        value = get_event_parameter(session, name)
        if isinstance(value, timedelta):
            print(f"{value.total_seconds()}s")
        else:
            print(value)


@simple_exception
def _set_event_parameters(
    name: EventParameter,
    value: timedelta | bool | str,
) -> None:
    from aimbat.lib.db import engine
    from aimbat.lib.event import set_event_parameter
    from sqlmodel import Session

    with Session(engine) as session:
        set_event_parameter(session, name, value)


app = App(name="event", help=__doc__, help_format="markdown")


@app.command(name="delete")
def cli_event_delete(
    event_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Delete existing event.

    Args:
        event_id: Event ID.
    """

    global_parameters = global_parameters or GlobalParameters()

    _delete_event(
        event_id,
    )


@app.command(name="list")
def cli_event_list(
    *,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print information on the events stored in AIMBAT."""

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    _print_event_table(table_parameters.short)


@app.command(name="activate")
def cli_event_activate(
    event_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Select the event to be active for Processing.

    Args:
        event_id: Event ID number.
    """

    global_parameters = global_parameters or GlobalParameters()

    _set_active_event_by_id(event_id)


@app.command(name="get")
def cli_event_parameter_get(
    name: EventParameter,
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Get parameter value for the active event.

    Args:
        name: Event parameter name.
    """

    global_parameters = global_parameters or GlobalParameters()

    _get_event_parameters(name)


@app.command(name="set")
def cli_event_parameter_set(
    name: EventParameter,
    value: timedelta | str,
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Set parameter value for the active event.

    Args:
        name: Event parameter name.
        value: Event parameter value.
    """

    global_parameters = global_parameters or GlobalParameters()

    _set_event_parameters(name, value)


@app.command(name="dump")
def cli_event_dump(
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Dump the contents of the AIMBAT event table to json."""

    global_parameters = global_parameters or GlobalParameters()

    _dump_event_table()


if __name__ == "__main__":
    app()
