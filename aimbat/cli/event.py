"""View and manage events in the AIMBAT project."""

from aimbat.lib.common import RegexEqual, debug_callback, ic
from aimbat.lib.types import (
    EventParameter,
    TEventParameterBool,
    TEventParameterTimedelta,
)
from typing import Annotated, overload
from datetime import timedelta
import typer


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


@overload
def _get_event_parameters(
    db_url: str | None, parameter_name: TEventParameterBool
) -> bool: ...
@overload
def _get_event_parameters(
    db_url: str | None, parameter_name: TEventParameterTimedelta
) -> timedelta: ...
def _get_event_parameters(
    db_url: str | None,
    parameter_name: EventParameter,
) -> bool | timedelta:
    from aimbat.lib.event import get_active_event
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        event = get_active_event(session)
        return getattr(event.parameters, parameter_name)


def _set_event_parameters(
    db_url: str | None,
    parameter_name: EventParameter,
    parameter_value: str,
) -> None:
    from aimbat.lib.event import get_active_event
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    value: float | timedelta

    match [parameter_name, RegexEqual(parameter_value)]:
        case ["window_pre" | "window_post", r"\d+\.+\d*" | r"\d+"]:
            value = timedelta(seconds=float(parameter_value))
        case ["completed", r"^[T,t]rue$" | r"^[Y,y]es$" | r"^[Y,y]$" | r"^1$"]:
            value = True
        case ["completed", r"^[F,f]alse$" | r"^[N,n]o$" | r"^[N,n]$" | r"^0$"]:
            value = False
        case _:
            raise RuntimeError(
                f"Unknown parameter {parameter_name=} or incorrect {parameter_value=}."
            )

    ic(parameter_name, parameter_value, value)

    with Session(engine_from_url(db_url)) as session:
        event = get_active_event(session)
        setattr(event.parameters, parameter_name, value)
        session.add(event)
        session.commit()


app = typer.Typer(
    name="event",
    callback=debug_callback,
    no_args_is_help=True,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)


@app.command("list")
def event_cli_list(ctx: typer.Context) -> None:
    """Print information on the events stored in AIMBAT."""
    db_url = ctx.obj["DB_URL"]
    _print_event_table(db_url=db_url)


@app.command("activate")
def event_cli_activate(
    ctx: typer.Context,
    event_id: Annotated[int, typer.Argument(help="Event ID number.")],
) -> None:
    """Select the event to be active for Processing."""
    db_url = ctx.obj["DB_URL"]
    _set_active_event(db_url=db_url, event_id=event_id)


@app.command("get")
def event_cli_parameter_get(
    ctx: typer.Context,
    name: Annotated[EventParameter, typer.Argument(help="Event parameter name.")],
) -> None:
    """Get parameter value for the active event."""

    db_url = ctx.obj["DB_URL"]
    print(_get_event_parameters(db_url=db_url, parameter_name=name))  # type: ignore


@app.command("set")
def event_cli_paramater_set(
    ctx: typer.Context,
    name: Annotated[EventParameter, typer.Argument(help="Event parameter name.")],
    value: str,
) -> None:
    """Set parameter value for the active event."""

    db_url = ctx.obj["DB_URL"]
    _set_event_parameters(db_url=db_url, parameter_name=name, parameter_value=value)


if __name__ == "__main__":
    app()
