from datetime import timedelta
from aimbat.lib.db import engine
from sqlmodel import Session, select
from aimbat.lib.models import AimbatSeismogram
from aimbat.lib.common import (
    AimbatParameterType,
    AimbatParameterName,
    AIMBAT_PARAMETER_NAMES,
    RegexEqual,
)
from datetime import datetime
import click


def get_parameter(
    session: Session, seismogram_id: int, parameter_name: str
) -> AimbatParameterType:
    select_seismogram = select(AimbatSeismogram).where(
        AimbatSeismogram.id == seismogram_id
    )
    aimbatseismogram = session.exec(select_seismogram).one()
    return getattr(aimbatseismogram.parameter, parameter_name)


def set_parameter(
    session: Session,
    seismogram_id: int,
    parameter_name: str,
    parameter_value: AimbatParameterType,
) -> None:
    select_seismogram = select(AimbatSeismogram).where(
        AimbatSeismogram.id == seismogram_id
    )
    aimbatseismogram = session.exec(select_seismogram).one()
    setattr(
        aimbatseismogram.parameter,
        parameter_name,
        parameter_value,
    )
    session.add(aimbatseismogram)
    session.commit()


@click.group("parameter")
def cli() -> None:
    """Manage parameters in the AIMBAT project."""
    pass


@cli.command("get")
@click.argument("seismogram_id", nargs=1, type=int, required=True)
@click.argument(
    "name", nargs=1, type=click.Choice(AIMBAT_PARAMETER_NAMES), required=True
)
def cli_get(seismogram_id: int, name: AimbatParameterName) -> None:
    """Get the value of a processing parameter."""

    with Session(engine) as session:
        print(get_parameter(session, seismogram_id, name))


@cli.command("set")
@click.argument(
    "seismogram_id",
    nargs=1,
    type=int,
    required=True,
)
@click.argument(
    "name", nargs=1, type=click.Choice(AIMBAT_PARAMETER_NAMES), required=True
)
@click.argument("value", nargs=1, type=str, required=True)
def cli_set(
    seismogram_id: int,
    name: AimbatParameterName,
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
            case ["window_pre" | "window_post", r"\d+\.+\d*" | r"\d+"]:
                timedelta_object = timedelta(seconds=float(value))
                set_parameter(session, seismogram_id, name, timedelta_object)
            case _:
                raise RuntimeError(
                    f"Unknown parameter name '{name}' or incorrect value '{value}'."
                )


if __name__ == "__main__":
    cli()
