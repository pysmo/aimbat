"""View and manage events in the AIMBAT project."""

from aimbat.cli.common import CommonParameters, convert_to_type
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


def _set_active_event(db_url: str | None, event_id: int) -> None:
    from aimbat.lib.event import set_active_event
    from aimbat.lib.common import engine_from_url
    from aimbat.lib.models import AimbatEvent
    from sqlmodel import Session, select

    with Session(engine_from_url(db_url)) as session:
        select_event = select(AimbatEvent).where(AimbatEvent.id == event_id)
        event = session.exec(select_event).one_or_none()
        if event is None:
            raise RuntimeError(f"No event with {event_id=} found.")
        set_active_event(session, event)


def _get_event_parameters(
    db_url: str | None,
    parameter_name: EventParameter,
) -> None:
    from aimbat.lib.event import get_active_event
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        event = get_active_event(session)
        value = getattr(event.parameters, parameter_name)
        if isinstance(value, timedelta):
            print(value.total_seconds())
        else:
            print(value)


def _set_event_parameters(
    db_url: str | None,
    parameter_name: EventParameter,
    parameter_value: str,
) -> None:
    from aimbat.lib.event import get_active_event
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    converted_value = convert_to_type(parameter_name, parameter_value)

    with Session(engine_from_url(db_url)) as session:
        event = get_active_event(session)
        setattr(event.parameters, parameter_name, converted_value)
        session.add(event)
        session.commit()


app = App(name="event", help=__doc__, help_format="markdown")


@app.command(name="list")
def event_cli_list(*, common: CommonParameters | None = None) -> None:
    """Print information on the events stored in AIMBAT."""

    common = common or CommonParameters()

    _print_event_table(common.db_url)


@app.command(name="activate")
def event_cli_activate(
    event_id: Annotated[int, Parameter(name="id")],
    *,
    common: CommonParameters | None = None,
) -> None:
    """Select the event to be active for Processing.

    Parameters:
        event_id: Event ID number.
    """

    common = common or CommonParameters()

    _set_active_event(common.db_url, event_id=event_id)


@app.command(name="get")
def event_cli_parameter_get(
    name: EventParameter,
    *,
    common: CommonParameters | None = None,
) -> None:
    """Get parameter value for the active event.

    Parameters:
        name: Event parameter name.
    """

    common = common or CommonParameters()

    _get_event_parameters(db_url=common.db_url, parameter_name=name)


@app.command(name="set")
def event_cli_paramater_set(
    name: EventParameter,
    value: str,
    *,
    common: CommonParameters | None = None,
) -> None:
    """Set parameter value for the active event.

    Parameters:
        name: Event parameter name.
        value: Event parameter value.
    """

    common = common or CommonParameters()

    _set_event_parameters(
        db_url=common.db_url, parameter_name=name, parameter_value=value
    )


if __name__ == "__main__":
    app()
