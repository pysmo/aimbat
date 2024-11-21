"""Module to manage and view events in AIMBAT."""

from aimbat.lib.common import RegexEqual, cli_enable_debug
from aimbat.lib.types import (
    AimbatEventParameterType,
    AimbatEventParameterName,
    AIMBAT_EVENT_PARAMETER_NAMES,
)
from datetime import timedelta
import click


def _event_print_table() -> None:
    from aimbat.lib.event import event_print_table

    event_print_table()


def _event_set_selected_event(event_id: int) -> None:
    from aimbat.lib.event import event_set_selected_event
    from aimbat.lib.db import engine
    from aimbat.lib.models import AimbatEvent
    from sqlmodel import Session, select

    with Session(engine) as session:
        select_event = select(AimbatEvent).where(AimbatEvent.id == event_id)
        event = session.exec(select_event).one_or_none()
        if event is None:
            raise RuntimeError(f"No event with {event_id=} found.")
        event_set_selected_event(session, event)


def _event_get_parameter(
    event_id: int, parameter_name: AimbatEventParameterName
) -> AimbatEventParameterType:
    from aimbat.lib.event import event_get_parameter
    from aimbat.lib.db import engine
    from sqlmodel import Session

    with Session(engine) as session:
        return event_get_parameter(session, event_id, parameter_name)


def _event_set_parameter(
    event_id: int,
    parameter_name: AimbatEventParameterName,
    parameter_value: AimbatEventParameterType,
) -> None:
    from aimbat.lib.event import event_set_parameter
    from aimbat.lib.db import engine
    from sqlmodel import Session

    with Session(engine) as session:
        event_set_parameter(session, event_id, parameter_name, parameter_value)


@click.group("event")
@click.pass_context
def event_cli(ctx: click.Context) -> None:
    """View and manage events in the AIMBAT project."""
    cli_enable_debug(ctx)


@event_cli.command("list")
def event_cli_list() -> None:
    """Print information on the events stored in AIMBAT."""
    _event_print_table()


@event_cli.command("select")
@click.argument("event_id", nargs=1, type=int, required=True)
def event_cli_select(event_id: int) -> None:
    """Select an event for Processing."""
    _event_set_selected_event(event_id)


@event_cli.group("parameter")
def event_cli_parameter() -> None:
    """Manage event parameters in the AIMBAT project."""
    pass


@event_cli_parameter.command("get")
@click.argument("event_id", nargs=1, type=int, required=True)
@click.argument(
    "name", nargs=1, type=click.Choice(AIMBAT_EVENT_PARAMETER_NAMES), required=True
)
def event_cli_parameter_get(event_id: int, name: AimbatEventParameterName) -> None:
    """Get the value of a processing parameter."""

    print(_event_get_parameter(event_id, name))


@event_cli_parameter.command("set")
@click.argument(
    "event_id",
    nargs=1,
    type=int,
    required=True,
)
@click.argument(
    "name", nargs=1, type=click.Choice(AIMBAT_EVENT_PARAMETER_NAMES), required=True
)
@click.argument("value", nargs=1, type=str, required=True)
def event_cli_paramater_set(
    event_id: int,
    name: AimbatEventParameterName,
    value: str,
) -> None:
    """Set value of a processing parameter."""

    match [name, RegexEqual(value)]:
        case ["window_pre" | "window_post", r"\d+\.+\d*" | r"\d+"]:
            timedelta_object = timedelta(seconds=float(value))
            _event_set_parameter(event_id, name, timedelta_object)
        case _:
            raise RuntimeError(
                f"Unknown parameter name '{name}' or incorrect value '{value}'."
            )


if __name__ == "__main__":
    event_cli()
