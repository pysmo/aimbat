"""Module to manage and view events in AIMBAT."""

from aimbat.lib.db import engine
from aimbat.lib.models import (
    AimbatEvent,
)
from aimbat.lib.common import RegexEqual
from typing import Literal, get_args
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select
from datetime import timedelta
import click


# Valid AIMBAT event parameter types and names
AimbatEventParameterType = timedelta
AimbatEventParameterName = Literal["window_pre", "window_post"]
AIMBAT_EVENT_PARAMETER_NAMES: tuple[AimbatEventParameterName, ...] = get_args(
    AimbatEventParameterName
)


def get_parameter(
    session: Session, event_id: int, parameter_name: AimbatEventParameterName
) -> AimbatEventParameterType:
    select_event = select(AimbatEvent).where(AimbatEvent.id == event_id)
    aimbatevent = session.exec(select_event).one()
    return getattr(aimbatevent.parameter, parameter_name)


def set_parameter(
    session: Session,
    event_id: int,
    parameter_name: AimbatEventParameterName,
    parameter_value: AimbatEventParameterType,
) -> None:
    select_event = select(AimbatEvent).where(AimbatEvent.id == event_id)
    aimbatevent = session.exec(select_event).one()
    setattr(aimbatevent.parameter, parameter_name, parameter_value)
    session.add(aimbatevent)
    session.commit()


def print_table() -> None:
    """Prints a pretty table with AIMBAT events."""

    table = Table(title="AIMBAT Events")

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Date & Time", justify="center", style="cyan", no_wrap=True)
    table.add_column("Latitude", justify="center", style="magenta")
    table.add_column("Longitude", justify="center", style="magenta")
    table.add_column("Depth", justify="center", style="magenta")
    table.add_column("# Seismograms", justify="center", style="green")
    table.add_column("# Stations", justify="center", style="green")

    with Session(engine) as session:
        for event in session.exec(select(AimbatEvent)).all():
            assert event.id is not None
            stations = {i.station_id for i in event.seismograms}
            table.add_row(
                str(event.id),
                str(event.time),
                str(event.latitude),
                str(event.longitude),
                str(event.depth),
                str(len(event.seismograms)),
                str(len(stations)),
            )

    console = Console()
    console.print(table)


@click.group("event")
def cli() -> None:
    """View and manage events in the AIMBAT project."""
    pass


@cli.command("list")
def cli_list() -> None:
    """Print information on the events stored in AIMBAT."""
    print_table()


@cli.group("parameter")
def cli_parameter() -> None:
    """Manage event parameters in the AIMBAT project."""
    pass


@cli_parameter.command("get")
@click.argument("event_id", nargs=1, type=int, required=True)
@click.argument(
    "name", nargs=1, type=click.Choice(AIMBAT_EVENT_PARAMETER_NAMES), required=True
)
def cli_parameter_get(event_id: int, name: AimbatEventParameterName) -> None:
    """Get the value of a processing parameter."""

    with Session(engine) as session:
        print(get_parameter(session, event_id, name))


@cli_parameter.command("set")
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
def cli_paramater_set(
    event_id: int,
    name: AimbatEventParameterName,
    value: str,
) -> None:
    """Set value of a processing parameter."""

    with Session(engine) as session:
        match [name, RegexEqual(value)]:
            case ["window_pre" | "window_post", r"\d+\.+\d*" | r"\d+"]:
                timedelta_object = timedelta(seconds=float(value))
                set_parameter(session, event_id, name, timedelta_object)
            case _:
                raise RuntimeError(
                    f"Unknown parameter name '{name}' or incorrect value '{value}'."
                )


if __name__ == "__main__":
    cli()
