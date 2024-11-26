from aimbat.lib.common import ic
from aimbat.lib.event import get_active_event
from aimbat.lib.models import (
    AimbatActiveEvent,
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramParameters,
)
from aimbat.lib.misc.rich_utils import make_table
from aimbat.lib.types import (
    SeismogramParameterName,
    SeismogramParameterType,
)
from rich.console import Console
from sqlmodel import Session, select
from typing import Sequence


def get_seismogram_parameter(
    session: Session, seismogram_id: int, parameter_name: SeismogramParameterName
) -> SeismogramParameterType:
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
    return getattr(aimbatseismogram.parameters, parameter_name)


def set_seismogram_parameter(
    session: Session,
    seismogram_id: int,
    parameter_name: SeismogramParameterName,
    parameter_value: SeismogramParameterType,
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
        aimbatseismogram.parameters,
        parameter_name,
        parameter_value,
    )
    session.add(aimbatseismogram)
    session.commit()


def get_selected_seismograms(
    session: Session, all_events: bool = False
) -> Sequence[AimbatSeismogram]:
    """Get the selected seismograms for the active avent.

    Parameters:
        session: Database session.
        all_events: Get the selected seismograms for all events.

    Returns: Selected seismograms.
    """

    ic()
    ic(session, all_events)

    select_events = (
        select(AimbatSeismogram)
        .join(AimbatSeismogramParameters)
        .join(AimbatEvent)
        .join(AimbatActiveEvent)
        .where(AimbatSeismogramParameters.select == 1)
        # .where(AimbatEvent.is_active == 1 and AimbatSeismogramParameters.select == 1)
    )
    if all_events:
        select_events = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameters)
            .where(AimbatSeismogramParameters.select == 1)
        )
    return session.exec(select_events).all()


def print_seismogram_table(session: Session, all_events: bool = False) -> None:
    """Prints a pretty table with AIMBAT seismograms."""

    ic()
    ic(session, all_events)

    title = "AIMBAT Seismograms"
    aimbat_seismograms = None

    if all_events:
        aimbat_seismograms = session.exec(select(AimbatSeismogram)).all()
    else:
        active_event = get_active_event(session)
        aimbat_seismograms = active_event.seismograms
        title = (
            f"AIMBAT seismograms for event {active_event.time} (ID={active_event.id})"
        )

    table = make_table(title=title)

    table.add_column("id", justify="right", style="cyan", no_wrap=True)
    table.add_column("Filename", justify="left", style="cyan", no_wrap=True)
    table.add_column("Station ID", justify="center", style="magenta")
    if all_events:
        table.add_column("Event ID", justify="center", style="magenta")

    for seismogram in aimbat_seismograms:
        if all_events:
            table.add_row(
                str(seismogram.id),
                str(seismogram.file.filename),
                str(seismogram.station.id),
                str(seismogram.event.id),
            )
        else:
            table.add_row(
                str(seismogram.id),
                str(seismogram.file.filename),
                str(seismogram.station.id),
            )

    console = Console()
    console.print(table)
