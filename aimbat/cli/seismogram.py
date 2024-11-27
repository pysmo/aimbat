"""View and manage seismograms in the AIMBAT project."""

from aimbat.lib.common import RegexEqual, debug_callback, ic
from aimbat.lib.types import (
    SeismogramParameter,
    TSeismogramParameterBool,
    TSeismogramParameterDatetime,
)
from datetime import datetime
from typing import Annotated, overload
import typer


@overload
def _get_seismogram_parameter(
    db_url: str | None, seismogram_id: int, parameter_name: TSeismogramParameterBool
) -> bool: ...


@overload
def _get_seismogram_parameter(
    db_url: str | None, seismogram_id: int, parameter_name: TSeismogramParameterDatetime
) -> datetime: ...


def _get_seismogram_parameter(
    db_url: str | None,
    seismogram_id: int,
    parameter_name: SeismogramParameter,
) -> bool | datetime:
    from aimbat.lib.seismogram import get_seismogram_parameter
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        return get_seismogram_parameter(session, seismogram_id, parameter_name)  # type: ignore


def _set_seismogram_parameter(
    db_url: str | None,
    seismogram_id: int,
    parameter_name: SeismogramParameter,
    parameter_value: str,
) -> None:
    from aimbat.lib.seismogram import set_seismogram_parameter
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    value: bool | datetime

    match [parameter_name, RegexEqual(parameter_value)]:
        case ["select", r"[T,t]rue$" | r"^[Y,y]es$" | r"^[Y,y]$" | r"^1$"]:
            value = True
        case ["select", r"^[F,f]alse$" | r"^[N,n]o$" | r"^[N,n]$" | r"^0$"]:
            value = False
        case ["t1" | "t2", r"\d\d\d\d[W,T,0-9,\-,:,\.,\s]+"]:
            value = datetime.fromisoformat(parameter_value)
        case _:
            raise RuntimeError(
                f"Unknown parameter name '{parameter_name}' or incorrect value '{parameter_value}'."
            )
    ic(parameter_name, parameter_value, value)

    with Session(engine_from_url(db_url)) as session:
        set_seismogram_parameter(session, seismogram_id, parameter_name, value)  # type: ignore


def _print_seismogram_table(db_url: str | None, all_events: bool) -> None:
    from aimbat.lib.seismogram import print_seismogram_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_seismogram_table(session, all_events)


app = typer.Typer(
    name="seismogram",
    no_args_is_help=True,
    callback=debug_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)


@app.command("list")
def seismogram_cli_list(
    ctx: typer.Context,
    all_events: Annotated[
        bool, typer.Option("--all", help="Select seismograms for all events.")
    ] = False,
) -> None:
    """Print information on the seismograms in the active event."""
    db_url = ctx.obj["DB_URL"]
    _print_seismogram_table(db_url, all_events)


@app.command("get")
def seismogram_cli_get(
    ctx: typer.Context,
    seismogram_id: Annotated[int, typer.Argument(help="Seismogram ID number.")],
    name: Annotated[
        SeismogramParameter, typer.Argument(help="Name of the seismogram parameter.")
    ],
) -> None:
    """Get the value of a processing parameter."""
    db_url = ctx.obj["DB_URL"]
    seismogram_parameter = _get_seismogram_parameter(
        db_url=db_url,
        seismogram_id=seismogram_id,
        parameter_name=name,  # type: ignore
    )
    print(seismogram_parameter)


@app.command("set")
def seismogram_cli_set(
    ctx: typer.Context,
    seismogram_id: Annotated[int, typer.Argument(help="Seismogram ID number.")],
    name: Annotated[
        SeismogramParameter, typer.Argument(help="Name of the seismogram parameter.")
    ],
    value: str,
) -> None:
    """Set value of a processing parameter."""
    db_url = ctx.obj["DB_URL"]
    _set_seismogram_parameter(
        db_url=db_url,
        seismogram_id=seismogram_id,
        parameter_name=name,
        parameter_value=value,
    )


if __name__ == "__main__":
    app()
