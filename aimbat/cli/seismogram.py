from aimbat.lib.db import engine
from aimbat.lib.common import RegexEqual, cli_enable_debug
from aimbat.lib.types import (
    AimbatSeismogramParameterName,
    AimbatSeismogramParameterType,
    AIMBAT_SEISMOGRAM_PARAMETER_NAMES,
)
from sqlmodel import Session
from datetime import datetime
import click


def _seismogram_get_parameter(
    session: Session, seismogram_id: int, parameter_name: AimbatSeismogramParameterName
) -> AimbatSeismogramParameterType:
    from aimbat.lib.seismogram import seismogram_get_parameter

    return seismogram_get_parameter(session, seismogram_id, parameter_name)


def _seismogram_set_parameter(
    session: Session,
    seismogram_id: int,
    parameter_name: AimbatSeismogramParameterName,
    parameter_value: AimbatSeismogramParameterType,
) -> None:
    from aimbat.lib.seismogram import seismogram_set_parameter

    seismogram_set_parameter(session, seismogram_id, parameter_name, parameter_value)


def _seismogram_print_table() -> None:
    from aimbat.lib.seismogram import seismogram_print_table

    seismogram_print_table()


@click.group("seismogram")
@click.pass_context
def seismogram_cli(ctx: click.Context) -> None:
    """View and manage seismograms in the AIMBAT project."""
    cli_enable_debug(ctx)


@seismogram_cli.command("list")
def seismogram_cli_list() -> None:
    """Print information on the seismograms stored in AIMBAT."""
    _seismogram_print_table()


@seismogram_cli.group("parameter")
def seismogram_cli_parameter() -> None:
    """Manage evennt parameters in the AIMBAT project."""
    pass


@seismogram_cli_parameter.command("get")
@click.argument("seismogram_id", nargs=1, type=int, required=True)
@click.argument(
    "name", nargs=1, type=click.Choice(AIMBAT_SEISMOGRAM_PARAMETER_NAMES), required=True
)
def seismogram_cli_paramter_get(
    seismogram_id: int, name: AimbatSeismogramParameterName
) -> None:
    """Get the value of a processing parameter."""

    with Session(engine) as session:
        print(_seismogram_get_parameter(session, seismogram_id, name))


@seismogram_cli_parameter.command("set")
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
def seismogram_cli_parameter_set(
    seismogram_id: int,
    name: AimbatSeismogramParameterName,
    value: str,
) -> None:
    """Set value of a processing parameter."""

    with Session(engine) as session:
        match [name, RegexEqual(value)]:
            case ["select", "True" | "true" | "yes" | "y"]:
                _seismogram_set_parameter(session, seismogram_id, name, True)
            case ["select", "False" | "false" | "no" | "n"]:
                _seismogram_set_parameter(session, seismogram_id, name, False)
            case ["t1" | "t2", r"\d\d\d\d[W,T,0-9,\-,:,\.,\s]+"]:
                datetime_object = datetime.fromisoformat(value)
                _seismogram_set_parameter(session, seismogram_id, name, datetime_object)
            case _:
                raise RuntimeError(
                    f"Unknown parameter name '{name}' or incorrect value '{value}'."
                )


if __name__ == "__main__":
    seismogram_cli(obj={})
