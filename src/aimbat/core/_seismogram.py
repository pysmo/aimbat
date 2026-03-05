import uuid
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pandas import Timestamp
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from typing import overload
from collections.abc import Sequence
from pydantic import TypeAdapter
from typing import Any, Literal
from pysmo import MiniSeismogram
from pysmo.functions import detrend, normalize, clone_to_mini
from pysmo.tools.plotutils import time_array
from pysmo.tools.azdist import distance
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramParameters,
)
from aimbat.models._parameters import AimbatSeismogramParametersBase
from aimbat._types import (
    SeismogramParameter,
    SeismogramParameterBool,
    SeismogramParameterTimestamp,
)

__all__ = [
    "delete_seismogram_by_id",
    "delete_seismogram",
    "get_seismogram_parameter_by_id",
    "get_seismogram_parameter",
    "set_seismogram_parameter_by_id",
    "set_seismogram_parameter",
    "reset_seismogram_parameters_by_id",
    "reset_seismogram_parameters",
    "get_selected_seismograms",
    "dump_seismogram_table_to_json",
    "dump_seismogram_parameter_table_to_json",
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


def reset_seismogram_parameters_by_id(
    session: Session, seismogram_id: uuid.UUID
) -> None:
    """Reset an AimbatSeismogram's parameters to their default values by ID.

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
    reset_seismogram_parameters(session, seismogram)


def reset_seismogram_parameters(session: Session, seismogram: AimbatSeismogram) -> None:
    """Reset an AimbatSeismogram's parameters to their default values.

    All fields defined on AimbatSeismogramParametersBase are reset to the
    values produced by a fresh default instance, so newly added fields are
    picked up automatically.

    Args:
        session: Database session.
        seismogram: Seismogram whose parameters should be reset.
    """

    logger.info(f"Resetting parameters for seismogram {seismogram.id}.")

    defaults = AimbatSeismogramParametersBase()
    for field_name in AimbatSeismogramParametersBase.model_fields:
        setattr(seismogram.parameters, field_name, getattr(defaults, field_name))
    session.add(seismogram)
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
    session: Session, event: AimbatEvent | None = None, all_events: bool = False
) -> Sequence[AimbatSeismogram]:
    """Get the selected seismograms for the given event.

    Args:
        session: Database session.
        event: Event to return selected seismograms for.
        all_events: Get the selected seismograms for all events.

    Returns: Selected seismograms.
    """

    logger.info("Getting selected AIMBAT seismograms.")

    if all_events is True:
        logger.debug("Selecting seismograms for all events.")
        statement = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameters)
            .where(AimbatSeismogramParameters.select == 1)
        )
    else:
        if event is None:
            raise ValueError("An event must be provided when all_events is False.")
        logger.debug(f"Selecting seismograms for event {event.id} only.")
        statement = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameters)
            .where(AimbatSeismogramParameters.select == 1)
            .where(AimbatSeismogram.event_id == event.id)
        )

    seismograms = session.exec(statement).all()

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


@overload
def dump_seismogram_parameter_table_to_json(
    session: Session,
    all_events: bool,
    as_string: Literal[True],
    event: AimbatEvent | None = None,
) -> str: ...


@overload
def dump_seismogram_parameter_table_to_json(
    session: Session,
    all_events: bool,
    as_string: Literal[False],
    event: AimbatEvent | None = None,
) -> list[dict[str, Any]]: ...


def dump_seismogram_parameter_table_to_json(
    session: Session,
    all_events: bool,
    as_string: bool,
    event: AimbatEvent | None = None,
) -> str | list[dict[str, Any]]:
    """Dump the seismogram parameter table data to json.

    Args:
        session: Database session.
        all_events: Include parameters for all events.
        as_string: Return as JSON string.
        event: Event to dump parameters for (only used when all_events is False).
    """

    logger.info("Dumping AimbatSeismogramParameters table to json.")

    adapter: TypeAdapter[Sequence[AimbatSeismogramParameters]] = TypeAdapter(
        Sequence[AimbatSeismogramParameters]
    )

    if all_events:
        parameters = session.exec(select(AimbatSeismogramParameters)).all()
    else:
        if event is None:
            raise ValueError("An event must be provided when all_events is False.")
        parameters = session.exec(
            select(AimbatSeismogramParameters)
            .join(AimbatSeismogram)
            .where(AimbatSeismogram.event_id == event.id)
        ).all()

    if as_string:
        return adapter.dump_json(parameters).decode("utf-8")
    return adapter.dump_python(parameters, mode="json")


@overload
def plot_all_seismograms(
    session: Session, event: AimbatEvent, return_fig: Literal[True]
) -> tuple[plt.Figure, plt.Axes]: ...


@overload
def plot_all_seismograms(
    session: Session, event: AimbatEvent, return_fig: Literal[False]
) -> None: ...


def plot_all_seismograms(
    session: Session, event: AimbatEvent, return_fig: bool
) -> tuple[plt.Figure, plt.Axes] | None:
    """Plot all seismograms for a particular event ordered by great circle distance.

    Args:
        session: Database session.
        event: AimbatEvent.
        return_fig: Whether to return the figure and axes objects instead of showing the plot.

    Returns:
        figure and axes objects if return_fig is True, otherwise None.
    """

    if len(seismograms := event.seismograms) == 0:
        raise RuntimeError(f"No seismograms found in event {event.id}.")

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

    fig, ax = plt.subplots()

    for seismogram in seismograms:
        clone = clone_to_mini(MiniSeismogram, seismogram)
        detrend(clone)
        normalize(clone)
        plot_data = clone.data * scaling_factor + distance_dict[seismogram.id]
        times = time_array(clone)
        ax.plot(
            times,
            plot_data,
            scalex=True,
            scaley=True,
        )
    plt.xlabel(xlabel=xlabel)
    plt.ylabel(ylabel=ylabel)
    plt.gcf().autofmt_xdate()
    fmt = mdates.DateFormatter("%H:%M:%S")
    plt.gca().xaxis.set_major_formatter(fmt)
    plt.title(title)
    if return_fig:
        return fig, ax
    plt.show()
    return None
