from aimbat.lib.common import logger
from aimbat.lib.event import get_active_event
from aimbat.lib.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramParameters,
)
from aimbat.lib.misc.rich_utils import make_table
from aimbat.lib.typing import (
    SeismogramParameter,
    SeismogramParameterBool,
    SeismogramParameterDatetime,
)
from datetime import datetime
from rich.console import Console
from sqlmodel import Session, select
from typing import overload
from collections.abc import Sequence


def get_seismogram_parameter_by_id(
    session: Session, seismogram_id: int, parameter_name: SeismogramParameter
) -> bool | datetime:
    """Get parameter value from an AimbatSeismogram by ID.

    Parameters:
        session: Database session.
        seismogram_id: Seismogram ID.
        parameter_name: Name of the parameter value to return.

    Returns:
        Seismogram parameter value.

    Raises:
        ValueError: If no AimbatSeismogram is found with the given ID.
    """

    logger.info(
        f"Getting seismogram {parameter_name=} for seismogram with id={seismogram_id}."
    )

    aimbat_seismogram = session.get(AimbatSeismogram, seismogram_id)

    if aimbat_seismogram is None:
        raise ValueError(f"No AimbatSeismogram found with {seismogram_id=}")

    return get_seismogram_parameter(aimbat_seismogram, parameter_name)


@overload
def get_seismogram_parameter(
    seismogram: AimbatSeismogram, parameter_name: SeismogramParameterBool
) -> bool: ...


@overload
def get_seismogram_parameter(
    seismogram: AimbatSeismogram, parameter_name: SeismogramParameterDatetime
) -> datetime: ...


@overload
def get_seismogram_parameter(
    seismogram: AimbatSeismogram, parameter_name: SeismogramParameter
) -> bool | datetime: ...


def get_seismogram_parameter(
    seismogram: AimbatSeismogram, parameter_name: SeismogramParameter
) -> bool | datetime:
    """Get parameter value from an AimbatSeismogram instance.

    Parameters:
        seismogram: Seismogram.
        parameter_name: Name of the parameter value to return.

    Returns:
        Seismogram parameter value.
    """

    logger.info(f"Getting seismogram {parameter_name=} value for {seismogram=}.")

    return getattr(seismogram.parameters, parameter_name)


def set_seismogram_parameter_by_id(
    session: Session,
    seismogram_id: int,
    parameter_name: SeismogramParameter,
    parameter_value: bool | datetime,
) -> None:
    """Set parameter value for an AimbatSeismogram by ID.

    Parameters:
        session: Database session
        seismogram_id: Seismogram id.
        parameter_name: Name of the parameter.
        parameter_value: Value to set.

    Raises:
        ValueError: If no AimbatSeismogram is found with the given ID.
    """

    logger.info(
        f"Setting seismogram {parameter_name=} to {parameter_value=} for seismogram with id={seismogram_id}."
    )

    aimbat_seismogram = session.get(AimbatSeismogram, seismogram_id)

    if aimbat_seismogram is None:
        raise ValueError(f"No AimbatSeismogram found with {seismogram_id=}")

    set_seismogram_parameter(
        session, aimbat_seismogram, parameter_name, parameter_value
    )


@overload
def set_seismogram_parameter(
    session: Session,
    seismogram: AimbatSeismogram,
    parameter_name: SeismogramParameterBool,
    parameter_value: bool,
) -> None: ...


@overload
def set_seismogram_parameter(
    session: Session,
    seismogram: AimbatSeismogram,
    parameter_name: SeismogramParameterDatetime,
    parameter_value: datetime,
) -> None: ...


@overload
def set_seismogram_parameter(
    session: Session,
    seismogram: AimbatSeismogram,
    parameter_name: SeismogramParameter,
    parameter_value: bool | datetime,
) -> None: ...


def set_seismogram_parameter(
    session: Session,
    seismogram: AimbatSeismogram,
    parameter_name: SeismogramParameter,
    parameter_value: bool | datetime,
) -> None:
    """Set parameter value for an AimbatSeismogram instance.

    Parameters:
        session: Database session
        seismogram: Seismogram to set parameter for.
        parameter_name: Name of the parameter.
        parameter_value: Value to set parameter to.

    """

    logger.info(
        f"Setting seismogram {parameter_name=} to {parameter_value=} in {seismogram=}."
    )

    setattr(
        seismogram.parameters,
        parameter_name,
        parameter_value,
    )
    session.add(seismogram)
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

    logger.info("Getting selected AIMBAT seismograms.")

    if all_events is True:
        logger.debug("Selecting seismograms for all events.")
        select_seismograms = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameters)
            .where(AimbatSeismogramParameters.select == 1)
        )
    else:
        logger.debug("Selecting seismograms for active event only.")
        select_seismograms = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameters)
            .join(AimbatEvent)
            .where(AimbatSeismogramParameters.select == 1)
            .where(AimbatEvent.active == 1)
        )

    seismograms = session.exec(select_seismograms).all()

    logger.debug(f"Found {len(seismograms)} selected seismograms.")

    return seismograms


def print_seismogram_table(session: Session, all_events: bool = False) -> None:
    """Prints a pretty table with AIMBAT seismograms.

    Parameters:
        session: Database session.
        all_events: Print seismograms for all events.
    """

    logger.info("Printing AIMBAT seismogram table.")

    title = "AIMBAT Seismograms"
    seismograms = None

    if all_events:
        logger.debug("Selecting seismograms for all events.")
        seismograms = session.exec(select(AimbatSeismogram)).all()
    else:
        logger.debug("Selecting seismograms for active event only.")
        active_event = get_active_event(session)
        seismograms = active_event.seismograms
        title = (
            f"AIMBAT seismograms for event {active_event.time} (ID={active_event.id})"
        )

    logger.debug(f"Found {len(seismograms)} seismograms for the table.")

    table = make_table(title=title)

    table.add_column("id", justify="right", style="cyan", no_wrap=True)
    table.add_column("Filename", justify="left", style="cyan", no_wrap=True)
    table.add_column("Station ID", justify="center", style="magenta")
    if all_events:
        table.add_column("Event ID", justify="center", style="magenta")

    for seismogram in seismograms:
        logger.debug(f"Adding seismogram with ID {seismogram.id} to the table.")
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
