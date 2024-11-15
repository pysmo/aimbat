from aimbat.lib.db import engine
from aimbat.lib.models import AimbatSeismogram
from aimbat.lib.common import RegexEqual, cli_enable_debug
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select
from datetime import datetime, timedelta
from typing import Literal, Tuple, get_args
from icecream import ic  # type: ignore
import click

ic.disable()

# Valid AIMBAT parameter types and names
AimbatSeismogramParameterType = float | datetime | timedelta | str
AimbatSeismogramParameterName = Literal["select", "t1", "t2"]
AIMBAT_SEISMOGRAM_PARAMETER_NAMES: Tuple[AimbatSeismogramParameterName, ...] = get_args(
    AimbatSeismogramParameterName
)


def get_parameter(
    session: Session, seismogram_id: int, parameter_name: AimbatSeismogramParameterName
) -> AimbatSeismogramParameterType:
    select_seismogram = select(AimbatSeismogram).where(
        AimbatSeismogram.id == seismogram_id
    )
    """Get parameter value from an AimbatSeismogram instance.

    Parameters:
        session: Database session
        seismogram_id: seismogram id to return paramter for.
        parameter_name: name of the parameter to return.

    Returns:
        Seismogram parameter value.
    """

    ic()
    ic(session, seismogram_id, parameter_name)

    aimbatseismogram = session.exec(select_seismogram).one()
    ic(aimbatseismogram)
    return getattr(aimbatseismogram.parameter, parameter_name)


def set_parameter(
    session: Session,
    seismogram_id: int,
    parameter_name: AimbatSeismogramParameterName,
    parameter_value: AimbatSeismogramParameterType,
) -> None:
    """Set parameter value for an AimbatSeismogram instance.

    Parameters:
        session: Database session
        seismogram_id: seismogram id to return paramter for.
        parameter_name: name of the parameter to return.
        parameter_value: value to set parameter to.

    """

    ic()
    ic(session, seismogram_id, parameter_name, parameter_value)

    select_seismogram = select(AimbatSeismogram).where(
        AimbatSeismogram.id == seismogram_id
    )
    aimbatseismogram = session.exec(select_seismogram).one()
    ic(aimbatseismogram)
    setattr(
        aimbatseismogram.parameter,
        parameter_name,
        parameter_value,
    )
    session.add(aimbatseismogram)
    session.commit()


def print_table() -> None:
    """Prints a pretty table with AIMBAT seismograms."""

    table = Table(title="AIMBAT Seismograms")

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Filename", justify="center", style="cyan", no_wrap=True)
    table.add_column("Station ID", justify="center", style="magenta")
    table.add_column("Event ID", justify="center", style="magenta")

    with Session(engine) as session:
        all_seismograms = session.exec(select(AimbatSeismogram)).all()
        if all_seismograms is not None:
            for seismogram in all_seismograms:
                assert seismogram.id is not None
                table.add_row(
                    str(seismogram.id),
                    str(seismogram.file.filename),
                    str(seismogram.station.id),
                    str(seismogram.event.id),
                )

    console = Console()
    console.print(table)


@click.group("seismogram")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """View and manage seismograms in the AIMBAT project."""
    cli_enable_debug(ctx)


@cli.command("list")
def cli_list() -> None:
    """Print information on the seismograms stored in AIMBAT."""
    print_table()


@cli.group("parameter")
def cli_paramater() -> None:
    """Manage evennt parameters in the AIMBAT project."""
    pass


@cli_paramater.command("get")
@click.argument("seismogram_id", nargs=1, type=int, required=True)
@click.argument(
    "name", nargs=1, type=click.Choice(AIMBAT_SEISMOGRAM_PARAMETER_NAMES), required=True
)
def cli_get(seismogram_id: int, name: AimbatSeismogramParameterName) -> None:
    """Get the value of a processing parameter."""

    with Session(engine) as session:
        print(get_parameter(session, seismogram_id, name))


@cli_paramater.command("set")
@click.argument(
    "seismogram_id",
    nargs=1,
    type=int,
    required=True,
)
@click.argument(
    "name", nargs=1, type=click.Choice(AIMBAT_SEISMOGRAM_PARAMETER_NAMES), required=True
)
@click.argument("value", nargs=1, type=str, required=True)
def cli_set(
    seismogram_id: int,
    name: AimbatSeismogramParameterName,
    value: str,
) -> None:
    """Set value of a processing parameter."""

    with Session(engine) as session:
        match [name, RegexEqual(value)]:
            case ["select", "True" | "true" | "yes" | "y"]:
                set_parameter(session, seismogram_id, name, True)
            case ["select", "False" | "false" | "no" | "n"]:
                set_parameter(session, seismogram_id, name, False)
            case ["t1" | "t2", r"\d\d\d\d[W,T,0-9,\-,:,\.,\s]+"]:
                datetime_object = datetime.fromisoformat(value)
                set_parameter(session, seismogram_id, name, datetime_object)
            case _:
                raise RuntimeError(
                    f"Unknown parameter name '{name}' or incorrect value '{value}'."
                )


if __name__ == "__main__":
    cli(obj={})
