from aimbat.lib.common import ic
from aimbat.lib.models import AimbatSeismogram
from aimbat.lib.types import (
    AimbatSeismogramParameterName,
    AimbatSeismogramParameterType,
)
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, select


def get_seismogram_parameter(
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


def set_seismogram_parameter(
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


def print_seismogram_table(session: Session) -> None:
    """Prints a pretty table with AIMBAT seismograms."""

    ic()
    ic(session)

    table = Table(title="AIMBAT Seismograms")

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Filename", justify="center", style="cyan", no_wrap=True)
    table.add_column("Station ID", justify="center", style="magenta")
    table.add_column("Event ID", justify="center", style="magenta")

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
