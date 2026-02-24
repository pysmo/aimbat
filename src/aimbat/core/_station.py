import uuid
from aimbat.core import get_active_event
from aimbat.logger import logger
from aimbat.utils import uuid_shortener, json_to_table, TABLE_STYLING
from aimbat.models import AimbatStation, AimbatSeismogram, AimbatEvent
from typing import overload, Literal, Any
from sqlmodel import Session, select, col
from sqlalchemy import func
from sqlalchemy.exc import NoResultFound
from collections.abc import Sequence
from pydantic import TypeAdapter

__all__ = [
    "delete_station_by_id",
    "delete_station",
    "get_stations_in_event",
    "get_stations_in_active_event",
    "get_stations_with_event_seismogram_count",
    "dump_station_table_to_json",
    "print_station_table",
]


def delete_station_by_id(session: Session, station_id: uuid.UUID) -> None:
    """Delete an AimbatStation from the database by ID.

    Args:
        session: Database session.
        station_id: Station ID.

    Raises:
        NoResultFound: If no AimbatStation is found with the given ID.
    """

    logger.debug(f"Getting station with id={station_id}.")

    station = session.get(AimbatStation, station_id)
    if station is None:
        raise NoResultFound(f"No AimbatStation found with {station_id=}")
    delete_station(session, station)


def delete_station(session: Session, station: AimbatStation) -> None:
    """Delete an AimbatStation from the database.

    Args:
        session: Database session.
        station: Station to delete.
    """

    logger.info(f"Deleting station {station.id}.")

    session.delete(station)
    session.commit()


@overload
def get_stations_in_active_event(
    session: Session, as_json: Literal[False]
) -> Sequence[AimbatStation]: ...


@overload
def get_stations_in_active_event(
    session: Session, as_json: Literal[True]
) -> list[dict[str, Any]]: ...


def get_stations_in_active_event(
    session: Session, as_json: bool
) -> Sequence[AimbatStation] | list[dict[str, Any]]:
    """Get the stations for the active event.

    Args:
        session: Database session.

    Returns: Stations in active event.
    """
    logger.info("Getting stations for active event.")

    statement = (
        select(AimbatStation)
        .distinct()
        .join(AimbatSeismogram)
        .join(AimbatEvent)
        .where(AimbatEvent.active == True)  # noqa: E712
    )

    logger.debug(f"Executing query: {statement}")
    results = session.exec(statement).all()

    if not as_json:
        return results

    adapter: TypeAdapter[Sequence[AimbatStation]] = TypeAdapter(Sequence[AimbatStation])

    return adapter.dump_python(results, mode="json")


def get_stations_in_event(
    session: Session, event: AimbatEvent
) -> Sequence[AimbatStation]:
    """Get the stations for a particular event.

    Args:
        session: Database session.
        event: Event to return stations for.

    Returns: Stations in event.
    """
    logger.info(f"Getting stations for event: {event.id}.")

    statement = (
        select(AimbatStation)
        .join(AimbatSeismogram)
        .join(AimbatEvent)
        .where(AimbatEvent.id == event.id)
    )

    logger.debug(f"Executing query: {statement}")
    stations = session.exec(statement).all()

    return stations


@overload
def get_stations_with_event_seismogram_count(
    session: Session, as_json: Literal[False]
) -> Sequence[tuple[AimbatStation, int, int]]: ...


@overload
def get_stations_with_event_seismogram_count(
    session: Session, as_json: Literal[True]
) -> list[dict[str, Any]]: ...


def get_stations_with_event_seismogram_count(
    session: Session, as_json: bool
) -> Sequence[tuple[AimbatStation, int, int]] | list[dict[str, Any]]:
    """Get stations along with the count of seismograms and events they are associated with.

    Args:
        session: Database session.
        as_json: Whether to return the result as JSON.

    Returns: A sequence of tuples containing the station, count of seismograms
        and count of events, or a JSON string if as_json is True.
    """
    logger.info("Getting stations with associated seismogram and event counts.")

    statement = (
        select(
            AimbatStation,
            func.count(col(AimbatSeismogram.id)),
            func.count(func.distinct(col(AimbatEvent.id))),
        )
        .select_from(AimbatStation)
        .join(AimbatSeismogram, isouter=True)
        .join(AimbatEvent, isouter=True)
        .group_by(col(AimbatStation.id))
    )

    logger.debug(f"Executing query: {statement}")
    results = session.exec(statement).all()

    if not as_json:
        return results

    formatted_results = []

    for row in results:
        # 1. Dump the station to a dict. mode="json" safely converts UUIDs/Datetimes to strings!
        station_dict = row[0].model_dump(mode="json")

        # 2. Add the counts directly to the dictionary
        station_dict["seismogram_count"] = row[1]
        station_dict["event_count"] = row[2]

        # 3. Add to our final list
        formatted_results.append(station_dict)

    return formatted_results


def dump_station_table_to_json(session: Session) -> str:
    """Create a JSON string from the AimbatStation table data."""

    logger.info("Dumping AIMBAT station table to json.")

    adapter: TypeAdapter[Sequence[AimbatStation]] = TypeAdapter(Sequence[AimbatStation])
    aimbat_station = session.exec(select(AimbatStation)).all()
    return adapter.dump_json(aimbat_station).decode("utf-8")


def print_station_table(
    session: Session, short: bool, all_events: bool = False
) -> None:
    """Prints a pretty table with AIMBAT stations.

    Args:
        session: Database session.
        short: Shorten and format the output to be more human-readable.
        all_events: Print stations for all events.
    """
    logger.info("Printing station table.")

    title = "AIMBAT stations for all events"

    if all_events:
        logger.debug("Selecting all AIMBAT stations.")
        data = get_stations_with_event_seismogram_count(session, as_json=True)
    else:
        logger.debug("Selecting AIMBAT stations used by active event.")
        active_event = get_active_event(session)
        data = get_stations_in_active_event(session, as_json=True)

        if short:
            title = f"AIMBAT stations for event {active_event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_shortener(session, active_event)})"
        else:
            title = (
                f"AIMBAT stations for event {active_event.time} (ID={active_event.id})"
            )

    column_order = [
        "id",
        "name",
        "network",
        "channel",
        "location",
        "latitude",
        "longitude",
        "elevation",
    ]
    if all_events:
        column_order.extend(["seismogram_count", "event_count"])

    column_kwargs: dict[str, dict[str, Any]] = {
        "id": {
            "header": "ID (shortened)" if short else "ID",
            "style": TABLE_STYLING.id,
            "justify": "center",
            "no_wrap": True,
        },
        "name": {
            "header": "Name",
            "style": TABLE_STYLING.mine,
            "justify": "center",
            "no_wrap": True,
        },
        "network": {
            "header": "Network",
            "style": TABLE_STYLING.mine,
            "justify": "center",
            "no_wrap": True,
        },
        "channel": {
            "header": "Channel",
            "style": TABLE_STYLING.mine,
            "justify": "center",
        },
        "location": {
            "header": "Location",
            "style": TABLE_STYLING.mine,
            "justify": "center",
        },
        "latitude": {
            "header": "Latitude",
            "style": TABLE_STYLING.mine,
            "justify": "center",
        },
        "longitude": {
            "header": "Longitude",
            "style": TABLE_STYLING.mine,
            "justify": "center",
        },
        "elevation": {
            "header": "Elevation",
            "style": TABLE_STYLING.mine,
            "justify": "center",
        },
        "seismogram_count": {
            "header": "# Seismograms",
            "style": TABLE_STYLING.linked,
            "justify": "center",
        },
        "event_count": {
            "header": "# Events",
            "style": TABLE_STYLING.linked,
            "justify": "center",
        },
    }

    formatters = {
        "id": lambda x: (
            uuid_shortener(session, AimbatStation, str_uuid=x) if short else str(x)
        ),
        "latitude": lambda x: f"{x:.3f}" if short else str(x),
        "longitude": lambda x: f"{x:.3f}" if short else str(x),
        "elevation": lambda x: f"{x:.0f}" if short else str(x),
    }

    json_to_table(
        data,
        title=title,
        column_order=column_order,
        column_kwargs=column_kwargs,
        formatters=formatters,
    )
