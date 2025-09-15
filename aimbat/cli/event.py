"""View and manage events in the AIMBAT project."""

from aimbat.cli.common import CommonParameters
from aimbat.lib.typing import EventParameter
from typing import Annotated
from datetime import timedelta
from cyclopts import App, Parameter


def _print_event_table(db_url: str | None) -> None:
    from aimbat.lib.event import print_event_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_event_table(session)


def _set_active_event_by_id(db_url: str | None, event_id: int) -> None:
    from aimbat.lib.event import set_active_event_by_id
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
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


@app.command(name="list")
def cli_event_list(*, common: CommonParameters | None = None) -> None:
    """Print information on the events stored in AIMBAT."""

    common = common or CommonParameters()

    _print_event_table(common.db_url)


@app.command(name="activate")
def cli_event_activate(
    event_id: Annotated[int, Parameter(name="id")],
    *,
    common: CommonParameters | None = None,
) -> None:
    """Select the event to be active for Processing.

    Parameters:
        event_id: Event ID number.
    """

    common = common or CommonParameters()

    _set_active_event_by_id(common.db_url, event_id=event_id)


@app.command(name="get")
def cli_event_parameter_get(
    name: EventParameter,
    *,
    common: CommonParameters | None = None,
) -> None:
    """Get parameter value for the active event.

    Parameters:
        name: Event parameter name.
    """

    common = common or CommonParameters()

    _get_event_parameters(db_url=common.db_url, name=name)


@app.command(name="set")
def cli_event_parameter_set(
    name: EventParameter,
    value: timedelta | str,
    *,
    common: CommonParameters | None = None,
) -> None:
    """Set parameter value for the active event.

    Parameters:
        name: Event parameter name.
        value: Event parameter value.
    """

    common = common or CommonParameters()

    _set_event_parameters(db_url=common.db_url, name=name, value=value)


if __name__ == "__main__":
    app()
