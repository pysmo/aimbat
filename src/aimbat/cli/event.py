"""View and manage events in the AIMBAT project."""

from aimbat.cli.common import GlobalParameters, TableParameters, simple_exception
from aimbat.cli.common import HINTS
from aimbat.aimbat_types import EventParameter
from typing import Annotated
from pandas import Timedelta
from cyclopts import App, Parameter
from sqlmodel import Session
import uuid


def string_to_event_uuid(session: Session, event_id: str) -> uuid.UUID:
    from aimbat.models import AimbatEvent
    from aimbat.utils import string_to_uuid

    return string_to_uuid(
        session,
        event_id,
        AimbatEvent,
        custom_error=f"Unable to find event using id: {event_id}. {HINTS.LIST_EVENTS}",
    )


app = App(name="event", help=__doc__, help_format="markdown")


@app.command(name="delete")
@simple_exception
def cli_event_delete(
    event_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Delete existing event.

    Args:
        event_id: Event ID.
    """
    from aimbat.db import engine
    from aimbat.core import delete_event_by_id

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        if not isinstance(event_id, uuid.UUID):
            event_id = string_to_event_uuid(session, event_id)
        delete_event_by_id(session, event_id)


@app.command(name="list")
@simple_exception
def cli_event_list(
    *,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print information on the events stored in AIMBAT."""
    from aimbat.db import engine
    from aimbat.core import print_event_table

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_event_table(session, table_parameters.short)


@app.command(name="activate")
@simple_exception
def cli_event_activate(
    event_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Select the event to be active for Processing.

    Args:
        event_id: Event ID number.
    """
    from aimbat.core import set_active_event_by_id
    from aimbat.db import engine

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        if not isinstance(event_id, uuid.UUID):
            event_id = string_to_event_uuid(session, event_id)
        set_active_event_by_id(session, event_id)


@app.command(name="get")
@simple_exception
def cli_event_parameter_get(
    name: EventParameter,
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Get parameter value for the active event.

    Args:
        name: Event parameter name.
    """

    from aimbat.db import engine
    from aimbat.core import get_event_parameter
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        value = get_event_parameter(session, name)
        if isinstance(value, Timedelta):
            print(f"{value.total_seconds()}s")
        else:
            print(value)


@app.command(name="set")
@simple_exception
def cli_event_parameter_set(
    name: EventParameter,
    value: Timedelta | str,
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Set parameter value for the active event.

    Args:
        name: Event parameter name.
        value: Event parameter value.
    """
    from aimbat.db import engine
    from aimbat.core import set_event_parameter
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        set_event_parameter(session, name, value)


@app.command(name="dump")
@simple_exception
def cli_event_dump(
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Dump the contents of the AIMBAT event table to json."""
    from aimbat.db import engine
    from aimbat.core import dump_event_table

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        dump_event_table(session)


if __name__ == "__main__":
    app()
