from aimbat.logger import logger
from aimbat.utils import (
    uuid_shortener,
    get_active_event,
    make_table,
    TABLE_STYLING,
    json_to_table,
)
from aimbat.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersBase,
)
from aimbat.aimbat_types import (
    SeismogramParameter,
    SeismogramParameterBool,
    SeismogramParameterTimestamp,
)
from pysmo import MiniSeismogram
from pysmo.functions import detrend, normalize, clone_to_mini
from pysmo.tools.plotutils import time_array, unix_time_array
from pysmo.tools.azdist import distance
from pandas import Timestamp
from rich.console import Console
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from typing import overload
from collections.abc import Sequence
from matplotlib.figure import Figure
from pydantic import TypeAdapter
from typing import Any, Literal
import aimbat.core._event as event
import uuid
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pyqtgraph as pg  # type: ignore

__all__ = [
    "delete_seismogram_by_id",
    "delete_seismogram",
    "get_seismogram_parameter_by_id",
    "get_seismogram_parameter",
    "set_seismogram_parameter_by_id",
    "set_seismogram_parameter",
    "get_selected_seismograms",
    "dump_seismogram_table_to_json",
    "print_seismogram_table",
    "dump_seismogram_parameter_table_to_json",
    "print_seismogram_parameter_table",
    "plot_all_seismograms",
]


def delete_seismogram_by_id(session: Session, seismogram_id: uuid.UUID) -> None:
    """Delete an AimbatSeismogram from the database by ID.

    Args:
        session: Database session.
        seismogram_id: Seismogram ID.

    Raises:
        NoResultFound: If no AimbatSeismogram is found with the given ID.
    """

    logger.debug(f"Getting seismogram with id={seismogram_id}.")

    seismogram = session.get(AimbatSeismogram, seismogram_id)
    if seismogram is None:
        raise NoResultFound(f"No AimbatSeismogram found with {seismogram_id=}")
    delete_seismogram(session, seismogram)


def delete_seismogram(session: Session, seismogram: AimbatSeismogram) -> None:
    """Delete an AimbatSeismogram from the database.

    Args:
        session: Database session.
        seismogram: Seismogram to delete.
    """

    logger.info(f"Deleting seismogram {seismogram.id}.")

    session.delete(seismogram)
    session.commit()


def get_seismogram_parameter_by_id(
    session: Session, seismogram_id: uuid.UUID, name: SeismogramParameter
) -> bool | Timestamp:
    """Get parameter value from an AimbatSeismogram by ID.

    Args:
        session: Database session.
        seismogram_id: Seismogram ID.
        name: Name of the parameter value to return.

    Returns:
        Seismogram parameter value.

    Raises:
        ValueError: If no AimbatSeismogram is found with the given ID.
    """

    logger.info(f"Getting seismogram {name=} for seismogram with id={seismogram_id}.")

    aimbat_seismogram = session.get(AimbatSeismogram, seismogram_id)

    if aimbat_seismogram is None:
        raise ValueError(f"No AimbatSeismogram found with {seismogram_id=}")

    return get_seismogram_parameter(aimbat_seismogram, name)


@overload
def get_seismogram_parameter(
    seismogram: AimbatSeismogram, name: SeismogramParameterBool
) -> bool: ...


@overload
def get_seismogram_parameter(
    seismogram: AimbatSeismogram, name: SeismogramParameterTimestamp
) -> Timestamp: ...


@overload
def get_seismogram_parameter(
    seismogram: AimbatSeismogram, name: SeismogramParameter
) -> bool | Timestamp: ...


def get_seismogram_parameter(
    seismogram: AimbatSeismogram, name: SeismogramParameter
) -> bool | Timestamp:
    """Get parameter value from an AimbatSeismogram instance.

    Args:
        seismogram: Seismogram.
        name: Name of the parameter value to return.

    Returns:
        Seismogram parameter value.
    """

    logger.info(f"Getting seismogram parameter {name=} value for {seismogram=}.")

    return getattr(seismogram.parameters, name)


def set_seismogram_parameter_by_id(
    session: Session,
    seismogram_id: uuid.UUID,
    name: SeismogramParameter,
    value: Timestamp | bool | str,
) -> None:
    """Set parameter value for an AimbatSeismogram by ID.

    Args:
        session: Database session
        seismogram_id: Seismogram id.
        name: Name of the parameter.
        value: Value to set.

    Raises:
        ValueError: If no AimbatSeismogram is found with the given ID.
    """

    logger.info(
        f"Setting seismogram {name=} to {value=} for seismogram with id={seismogram_id}."
    )

    aimbat_seismogram = session.get(AimbatSeismogram, seismogram_id)

    if aimbat_seismogram is None:
        raise ValueError(f"No AimbatSeismogram found with {seismogram_id=}")

    set_seismogram_parameter(session, aimbat_seismogram, name, value)


@overload
def set_seismogram_parameter(
    session: Session,
    seismogram: AimbatSeismogram,
    name: SeismogramParameterBool,
    value: bool | str,
) -> None: ...


@overload
def set_seismogram_parameter(
    session: Session,
    seismogram: AimbatSeismogram,
    name: SeismogramParameterTimestamp,
    value: Timestamp,
) -> None: ...


@overload
def set_seismogram_parameter(
    session: Session,
    seismogram: AimbatSeismogram,
    name: SeismogramParameter,
    value: Timestamp | bool | str,
) -> None: ...


def set_seismogram_parameter(
    session: Session,
    seismogram: AimbatSeismogram,
    name: SeismogramParameter,
    value: Timestamp | bool | str,
) -> None:
    """Set parameter value for an AimbatSeismogram instance.

    Args:
        session: Database session
        seismogram: Seismogram to set parameter for.
        name: Name of the parameter.
        value: Value to set parameter to.

    """

    logger.info(f"Setting seismogram {name=} to {value=} in {seismogram=}.")

    parameters = AimbatSeismogramParametersBase.model_validate(
        seismogram.parameters, update={name: value}
    )
    setattr(seismogram.parameters, name, getattr(parameters, name))
    session.add(seismogram)
    session.commit()


def get_selected_seismograms(
    session: Session, all_events: bool = False
) -> Sequence[AimbatSeismogram]:
    """Get the selected seismograms for the active avent.

    Args:
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


def dump_seismogram_table_to_json(session: Session) -> str:
    """Create a JSON string from the AimbatSeismogram table data."""

    logger.info("Dumping AIMBAT seismogram table to json.")
    adapter: TypeAdapter[Sequence[AimbatSeismogram]] = TypeAdapter(
        Sequence[AimbatSeismogram]
    )
    aimbat_seismograms = session.exec(select(AimbatSeismogram)).all()

    return adapter.dump_json(aimbat_seismograms).decode("utf-8")


def print_seismogram_table(
    session: Session, short: bool, all_events: bool = False
) -> None:
    """Prints a pretty table with AIMBAT seismograms.

    Args:
        short: Shorten and format the output to be more human-readable.
        all_events: Print seismograms for all events.
    """

    logger.info("Printing AIMBAT seismogram table.")

    title = "AIMBAT seismograms for all events"
    seismograms = None

    if all_events:
        logger.debug("Selecting seismograms for all events.")
        seismograms = session.exec(select(AimbatSeismogram)).all()
    else:
        logger.debug("Selecting seismograms for active event only.")
        active_event = get_active_event(session)
        seismograms = active_event.seismograms
        if short:
            title = f"AIMBAT seismograms for event {active_event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={event.uuid_shortener(session, active_event)})"
        else:
            title = f"AIMBAT seismograms for event {active_event.time} (ID={active_event.id})"

    logger.debug(f"Found {len(seismograms)} seismograms for the table.")

    table = make_table(title=title)
    table.add_column(
        "ID (shortened)" if short else "ID",
        justify="center",
        style=TABLE_STYLING.id,
        no_wrap=True,
    )
    table.add_column(
        "Selected", justify="center", style=TABLE_STYLING.mine, no_wrap=True
    )
    table.add_column("NPTS", justify="center", style=TABLE_STYLING.mine, no_wrap=True)
    table.add_column("Delta", justify="center", style=TABLE_STYLING.mine, no_wrap=True)
    table.add_column(
        "Data ID", justify="center", style=TABLE_STYLING.linked, no_wrap=True
    )
    table.add_column("Station ID", justify="center", style=TABLE_STYLING.linked)
    table.add_column("Station Name", justify="center", style=TABLE_STYLING.linked)
    if all_events:
        table.add_column("Event ID", justify="center", style=TABLE_STYLING.linked)

    for seismogram in seismograms:
        logger.debug(f"Adding seismogram with ID {seismogram.id} to the table.")
        row = [
            (uuid_shortener(session, seismogram) if short else str(seismogram.id)),
            TABLE_STYLING.bool_formatter(seismogram.parameters.select),
            str(len(seismogram)),
            str(seismogram.delta.total_seconds()),
            (
                uuid_shortener(session, seismogram.datasource)
                if short
                else str(seismogram.datasource.id)
            ),
            (
                uuid_shortener(session, seismogram.station)
                if short
                else str(seismogram.station.id)
            ),
            f"{seismogram.station.name} - {seismogram.station.network}",
        ]

        if all_events:
            row.append(
                uuid_shortener(session, seismogram.event)
                if short
                else str(seismogram.event.id)
            )
        table.add_row(*row)

    console = Console()
    console.print(table)


@overload
def dump_seismogram_parameter_table_to_json(
    session: Session, all_events: bool, as_string: Literal[True]
) -> str: ...


@overload
def dump_seismogram_parameter_table_to_json(
    session: Session, all_events: bool, as_string: Literal[False]
) -> list[dict[str, Any]]: ...


def dump_seismogram_parameter_table_to_json(
    session: Session, all_events: bool, as_string: bool
) -> str | list[dict[str, Any]]:
    """Dump the seismogram parameter table data to json."""

    logger.info("Dumping AimbatSeismogramParameters table to json.")

    adapter: TypeAdapter[Sequence[AimbatSeismogramParameters]] = TypeAdapter(
        Sequence[AimbatSeismogramParameters]
    )

    if all_events:
        parameters = session.exec(select(AimbatSeismogramParameters)).all()
    else:
        parameters = session.exec(
            select(AimbatSeismogramParameters)
            .join(AimbatSeismogram)
            .join(AimbatEvent)
            .where(AimbatEvent.active == 1)
        ).all()

    if as_string:
        return adapter.dump_json(parameters).decode("utf-8")
    return adapter.dump_python(parameters, mode="json")


def print_seismogram_parameter_table(session: Session, short: bool) -> None:
    """Print a pretty table with AIMBAT seismogram parameter values for the active event.

    Args:
        short: Shorten and format the output to be more human-readable.
    """

    logger.info("Printing AIMBAT seismogram parameters table for active event.")

    active_event = get_active_event(session)
    title = f"Seismogram parameters for event: {uuid_shortener(session, active_event) if short else str(active_event.id)}"

    json_to_table(
        data=dump_seismogram_parameter_table_to_json(
            session, all_events=False, as_string=False
        ),
        title=title,
        skip_keys=["id"],
        column_order=["seismogram_id", "select"],
        common_column_kwargs={"highlight": True},
        formatters={
            "seismogram_id": lambda x: (
                uuid_shortener(session, AimbatSeismogram, str_uuid=x) if short else x
            ),
        },
        column_kwargs={
            "seismogram_id": {
                "header": "Seismogram ID (shortened)" if short else "Seismogram ID",
                "justify": "center",
                "style": TABLE_STYLING.mine,
            },
        },
    )


def plot_all_seismograms(session: Session, use_qt: bool = False) -> Figure:
    """Plot all seismograms for a particular event ordered by great circle distance.

    Args:
        use_qt: Plot with pqtgraph instead of pyplot
    """

    active_event = get_active_event(session)

    if active_event is None:
        raise RuntimeError("No active event set.")

    seismograms = active_event.seismograms

    if len(seismograms) == 0:
        raise RuntimeError("No seismograms found in active event.")

    distance_dict = {
        seismogram.id: distance(seismogram.station, seismogram.event) / 1000
        for seismogram in seismograms
    }
    distance_min = min(distance_dict.values())
    distance_max = max(distance_dict.values())
    scaling_factor = (distance_max - distance_min) / len(seismograms) * 5

    title = seismograms[0].event.time.strftime("Event %Y-%m-%d %H:%M:%S")
    xlabel = "Time of day"
    ylabel = "Epicentral distance [km]"

    plot_widget = None
    if use_qt:
        plot_widget = pg.plot(title=title)
        axis = pg.DateAxisItem()
        plot_widget.setAxisItems({"bottom": axis})
        plot_widget.setLabel("bottom", xlabel)
        plot_widget.setLabel("left", ylabel)
    else:
        fig, ax = plt.subplots()

    for seismogram in seismograms:
        clone = clone_to_mini(MiniSeismogram, seismogram)
        detrend(clone)
        normalize(clone)
        plot_data = clone.data * scaling_factor + distance_dict[seismogram.id]
        if use_qt and plot_widget is not None:
            times = unix_time_array(clone)
            plot_widget.plot(times, plot_data)
        else:
            times = time_array(clone)
            ax.plot(
                times,
                plot_data,
                scalex=True,
                scaley=True,
            )
    if not use_qt:
        plt.xlabel(xlabel=xlabel)
        plt.ylabel(ylabel=ylabel)
        plt.gcf().autofmt_xdate()
        fmt = mdates.DateFormatter("%H:%M:%S")
        plt.gca().xaxis.set_major_formatter(fmt)
        plt.title(title)
        plt.show()
    return fig
