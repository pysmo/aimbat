from aimbat.lib.common import (
    logger,
    check_for_notebook,
    reverse_uuid_shortener,
)
from aimbat.lib.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersBase,
)
from aimbat.lib.typing import (
    SeismogramParameter,
    SeismogramParameterBool,
    SeismogramParameterDatetime,
)
from aimbat.lib.misc.rich_utils import make_table
from pysmo import MiniSeismogram
from pysmo.functions import detrend, normalize, clone_to_mini
from pysmo.tools.plotutils import time_array, unix_time_array
from pysmo.tools.azdist import distance
from datetime import datetime
from rich.console import Console
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from typing import overload, Literal
from collections.abc import Sequence
from pyqtgraph.jupyter import PlotWidget  # type: ignore
from matplotlib.figure import Figure
import aimbat.lib.data as data
import aimbat.lib.event as event
import aimbat.lib.station as station
import uuid
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pyqtgraph as pg  # type: ignore


def seismogram_uuid_dict_reversed(
    session: Session, min_length: int = 2
) -> dict[uuid.UUID, str]:
    return reverse_uuid_shortener(
        session.exec(select(AimbatSeismogram.id)).all(), min_length
    )


def delete_seismogram_by_id(session: Session, seismogram_id: uuid.UUID) -> None:
    """Delete an AimbatSeismogram from the database by ID.

    Parameters:
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

    Parameters:
        session: Database session.
        seismogram: Seismogram to delete.
    """

    logger.info(f"Deleting seismogram {seismogram.id}.")

    session.delete(seismogram)
    session.commit()


def get_seismogram_parameter_by_id(
    session: Session, seismogram_id: uuid.UUID, name: SeismogramParameter
) -> bool | datetime:
    """Get parameter value from an AimbatSeismogram by ID.

    Parameters:
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
    seismogram: AimbatSeismogram, name: SeismogramParameterDatetime
) -> datetime: ...


@overload
def get_seismogram_parameter(
    seismogram: AimbatSeismogram, name: SeismogramParameter
) -> bool | datetime: ...


def get_seismogram_parameter(
    seismogram: AimbatSeismogram, name: SeismogramParameter
) -> bool | datetime:
    """Get parameter value from an AimbatSeismogram instance.

    Parameters:
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
    value: datetime | bool | str,
) -> None:
    """Set parameter value for an AimbatSeismogram by ID.

    Parameters:
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
    name: SeismogramParameterDatetime,
    value: datetime,
) -> None: ...


@overload
def set_seismogram_parameter(
    session: Session,
    seismogram: AimbatSeismogram,
    name: SeismogramParameter,
    value: datetime | bool | str,
) -> None: ...


def set_seismogram_parameter(
    session: Session,
    seismogram: AimbatSeismogram,
    name: SeismogramParameter,
    value: datetime | bool | str,
) -> None:
    """Set parameter value for an AimbatSeismogram instance.

    Parameters:
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


def print_seismogram_table(
    session: Session, format: bool, all_events: bool = False
) -> None:
    """Prints a pretty table with AIMBAT seismograms.

    Parameters:
        session: Database session.
        format: Print the output in a more human-readable format.
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
        active_event = event.get_active_event(session)
        seismograms = active_event.seismograms
        if format:
            title = f"AIMBAT seismograms for event {active_event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={event.uuid_dict_reversed(session)[active_event.id]})"
        else:
            title = f"AIMBAT seismograms for event {active_event.time} (ID={active_event.id})"

    logger.debug(f"Found {len(seismograms)} seismograms for the table.")

    table = make_table(title=title)
    if format:
        table.add_column("id (shortened)", justify="center", style="cyan", no_wrap=True)
    else:
        table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Selected", justify="center", style="cyan", no_wrap=True)
    table.add_column("File ID", justify="center", style="cyan", no_wrap=True)
    table.add_column("Delta", justify="center", style="cyan", no_wrap=True)
    table.add_column("NPTS", justify="center", style="cyan", no_wrap=True)
    table.add_column("Station ID", justify="center", style="magenta")
    table.add_column("Station Name", justify="center", style="magenta")
    if all_events:
        table.add_column("Event ID", justify="center", style="magenta")

    for seismogram in seismograms:
        logger.debug(f"Adding seismogram with ID {seismogram.id} to the table.")
        row = [
            (
                seismogram_uuid_dict_reversed(session)[seismogram.id]
                if format
                else str(seismogram.id)
            ),
            ":heavy_check_mark:" if seismogram.parameters.select is True else "",
            (
                data.file_uuid_dict_reversed(session)[seismogram.file.id]
                if format
                else str(seismogram.file.id)
            ),
            str(seismogram.delta.total_seconds()),
            str(len(seismogram)),
            (
                station.station_uuid_dict_reversed(session)[seismogram.station.id]
                if format
                else str(seismogram.station.id)
            ),
            f"{seismogram.station.name} - {seismogram.station.network}",
        ]

        if all_events:
            row.append(
                event.uuid_dict_reversed(session)[seismogram.event.id]
                if format
                else str(seismogram.event.id)
            )
        table.add_row(*row)

    console = Console()
    console.print(table)


@overload
def plot_seismograms(session: Session, use_qt: Literal[True]) -> PlotWidget: ...
@overload
def plot_seismograms(session: Session, use_qt: Literal[False] = False) -> Figure: ...
@overload
def plot_seismograms(session: Session, use_qt: bool = False) -> Figure | PlotWidget: ...
def plot_seismograms(session: Session, use_qt: bool = False) -> Figure | PlotWidget:
    """Plot all seismograms for a particular event ordered by great circle distance.

    Parameters:
        session: Database session.
    """

    active_event = event.get_active_event(session)

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
        if check_for_notebook():
            plot_widget = PlotWidget(width=200)
        else:
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
    if use_qt and isinstance(plot_widget, PlotWidget):
        return plot_widget
    elif not use_qt:
        plt.xlabel(xlabel=xlabel)
        plt.ylabel(ylabel=ylabel)
        plt.gcf().autofmt_xdate()
        fmt = mdates.DateFormatter("%H:%M:%S")
        plt.gca().xaxis.set_major_formatter(fmt)
        plt.title(title)
        plt.show()
    return fig
