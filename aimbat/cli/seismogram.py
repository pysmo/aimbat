"""View and manage seismograms in the AIMBAT project."""

from aimbat.lib.common import RegexEqual, debug_callback, ic
from aimbat.lib.types import (
    SeismogramParameterName,
    SeismogramParameterType,
    SEISMOGRAM_PARAMETER_NAMES,
)
from datetime import datetime
from enum import StrEnum
from typing import Annotated
import typer


ParameterName = StrEnum(  # type: ignore
    "ParameterName",
    [(i, i) for i in SEISMOGRAM_PARAMETER_NAMES],
)


def _get_seismogram_parameter(
    seismogram_id: int,
    parameter_name: SeismogramParameterName,
    db_url: str | None,
) -> SeismogramParameterType:
    from aimbat.lib.seismogram import get_seismogram_parameter
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        return get_seismogram_parameter(session, seismogram_id, parameter_name)


def _set_seismogram_parameter(
    seismogram_id: int,
    parameter_name: SeismogramParameterName,
    parameter_value: str,
    db_url: str | None,
) -> None:
    from aimbat.lib.seismogram import set_seismogram_parameter
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    value: SeismogramParameterType

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
        set_seismogram_parameter(session, seismogram_id, parameter_name, value)


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
    sid: Annotated[int, typer.Argument(help="Seismogram ID number.")],
    name: Annotated[
        ParameterName, typer.Argument(help="Name of the seismogram parameter.")
    ],
) -> None:
    """Get the value of a processing parameter."""
    db_url = ctx.obj["DB_URL"]
    print(
        _get_seismogram_parameter(seismogram_id=sid, parameter_name=name, db_url=db_url)  # type: ignore
    )


@app.command("set")
def seismogram_cli_set(
    ctx: typer.Context,
    sid: Annotated[int, typer.Argument(help="Seismogram ID number.")],
    name: Annotated[
        ParameterName, typer.Argument(help="Name of the seismogram parameter.")
    ],
    value: str,
) -> None:
    """Set value of a processing parameter."""
    db_url = ctx.obj["DB_URL"]
    _set_seismogram_parameter(
        seismogram_id=sid,
        parameter_name=name,  # type: ignore
        parameter_value=value,
        db_url=db_url,
    )


if __name__ == "__main__":
    app()
