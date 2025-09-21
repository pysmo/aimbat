"""View and manage events in the AIMBAT project."""

from aimbat.cli.common import GlobalParameters, TableParameters
from aimbat.lib.typing import EventParameter
from typing import Annotated
from datetime import timedelta
from cyclopts import App, Parameter
import uuid


def _delete_event(
    db_url: str | None,
    event_id: uuid.UUID | str,
) -> None:
    from aimbat.lib.event import delete_event_by_id
    from aimbat.lib.common import engine_from_url, string_to_uuid
    from aimbat.lib.models import AimbatEvent
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        if not isinstance(event_id, uuid.UUID):
            event_id = string_to_uuid(session, event_id, AimbatEvent)
        delete_event_by_id(session, event_id)


def _print_event_table(db_url: str | None, format: bool) -> None:
    from aimbat.lib.event import print_event_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_event_table(session, format)


def _set_active_event_by_id(db_url: str | None, event_id: uuid.UUID | str) -> None:
    from aimbat.lib.event import set_active_event_by_id
    from aimbat.lib.common import engine_from_url, string_to_uuid
    from aimbat.lib.models import AimbatEvent
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        if not isinstance(event_id, uuid.UUID):
            event_id = string_to_uuid(session, event_id, AimbatEvent)
        set_active_event_by_id(session, event_id)


def _get_event_parameters(
    db_url: str | None,
    name: EventParameter,
) -> None:
    from aimbat.lib.event import get_event_parameter
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        value = get_event_parameter(session, name)
        if isinstance(value, timedelta):
            print(f"{value.total_seconds()}s")
        else:
            print(value)


def _set_event_parameters(
    db_url: str | None,
    name: EventParameter,
    value: timedelta | bool | str,
) -> None:
    from aimbat.lib.event import set_event_parameter
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        set_event_parameter(session, name, value)


app = App(name="event", help=__doc__, help_format="markdown")


@app.command(name="delete")
def cli_event_delete(
    event_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Delete existing event.

    Parameters:
        event_id: Event ID.
    """

    global_parameters = global_parameters or GlobalParameters()

    _delete_event(
        db_url=global_parameters.db_url,
        event_id=event_id,
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

    _print_event_table(global_parameters.db_url, table_parameters.format)


@app.command(name="activate")
def cli_event_activate(
    event_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Select the event to be active for Processing.

    Parameters:
        event_id: Event ID number.
    """

    global_parameters = global_parameters or GlobalParameters()

    _set_active_event_by_id(global_parameters.db_url, event_id=event_id)


@app.command(name="get")
def cli_event_parameter_get(
    name: EventParameter,
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Get parameter value for the active event.

    Parameters:
        name: Event parameter name.
    """

    global_parameters = global_parameters or GlobalParameters()

    _get_event_parameters(db_url=global_parameters.db_url, name=name)


@app.command(name="set")
def cli_event_parameter_set(
    name: EventParameter,
    value: timedelta | str,
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Set parameter value for the active event.

    Parameters:
        name: Event parameter name.
        value: Event parameter value.
    """

    global_parameters = global_parameters or GlobalParameters()

    _set_event_parameters(db_url=global_parameters.db_url, name=name, value=value)


if __name__ == "__main__":
    app()
