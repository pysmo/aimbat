import uuid
from collections.abc import Sequence
from typing import Any, Literal, overload

from pydantic import TypeAdapter
from sqlalchemy import func
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col, select

from aimbat.logger import logger
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatStation

__all__ = [
    "delete_station_by_id",
    "delete_station",
    "get_stations_in_event",
    "dump_station_table_to_json",
    "dump_station_table_with_counts",
    "get_stations_with_event_and_seismogram_count",
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
def get_stations_in_event(
    session: Session, event: AimbatEvent, as_json: Literal[False] = ...
) -> Sequence[AimbatStation]: ...


@overload
def get_stations_in_event(
    session: Session, event: AimbatEvent, as_json: Literal[True]
) -> list[dict[str, Any]]: ...


def get_stations_in_event(
    session: Session, event: AimbatEvent, as_json: bool = False
) -> Sequence[AimbatStation] | list[dict[str, Any]]:
    """Get the stations for a particular event.

    Args:
        session: Database session.
        event: Event to return stations for.
        as_json: Whether to return the result as JSON.

    Returns: Stations in event.
    """
    logger.info(f"Getting stations for event: {event.id}.")

    statement = (
        select(AimbatStation)
        .distinct()
        .join(AimbatSeismogram)
        .where(AimbatSeismogram.event_id == event.id)
    )

    logger.debug(f"Executing query: {statement}")
    results = session.exec(statement).all()

    if not as_json:
        return results

    adapter: TypeAdapter[Sequence[AimbatStation]] = TypeAdapter(Sequence[AimbatStation])

    return adapter.dump_python(results, mode="json")


def get_stations_with_event_and_seismogram_count(
    session: Session,
) -> Sequence[tuple[AimbatStation, int, int]]:
    """Get stations along with the count of seismograms and events they are associated with.

    Args:
        session: Database session.

    Returns: A sequence of tuples containing the station, count of seismograms
        and count of events.
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
    return session.exec(statement).all()


def dump_station_table_with_counts(session: Session) -> list[dict[str, Any]]:
    """Dump station table with associated seismogram and event counts to a list of dicts.

    Each dict represents a station and includes additional keys for the
    seismogram and event counts.

    Args:
        session: Database session.

    Returns: A list of dictionaries representing the stations with counts.
    """
    results = get_stations_with_event_and_seismogram_count(session)
    formatted_results = []

    for row in results:
        station_dict = row[0].model_dump(mode="json")
        station_dict["seismogram_count"] = row[1]
        station_dict["event_count"] = row[2]
        formatted_results.append(station_dict)

    return formatted_results


def dump_station_table_to_json(session: Session) -> str:
    """Create a JSON string from the AimbatStation table data."""

    logger.info("Dumping AIMBAT station table to json.")

    adapter: TypeAdapter[Sequence[AimbatStation]] = TypeAdapter(Sequence[AimbatStation])
    aimbat_station = session.exec(select(AimbatStation)).all()
    return adapter.dump_json(aimbat_station).decode("utf-8")
