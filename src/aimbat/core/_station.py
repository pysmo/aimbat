"""Functions for managing and querying stations in AIMBAT."""

from collections.abc import Sequence
from typing import Any, Literal, overload
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramQuality,
    AimbatStation,
    AimbatStationRead,
    SeismogramQualityStats,
)
from aimbat.utils import get_title_map, rel

__all__ = [
    "delete_station",
    "get_stations_in_event",
    "get_station_iccs_ccs",
    "get_station_quality",
    "dump_station_table",
    "dump_station_quality_table",
]


def delete_station(session: Session, station_id: UUID) -> None:
    """Delete an AimbatStation from the database.

    Args:
        session: Database session.
        station_id: ID of the station to delete.
    """

    logger.info(f"Deleting station with id={station_id}.")

    station = session.get(AimbatStation, station_id)
    if station is None:
        raise NoResultFound(f"No AimbatStation found with {station_id=}")

    session.delete(station)
    session.commit()


@overload
def get_stations_in_event(
    session: Session, event_id: UUID, as_json: Literal[False] = ...
) -> Sequence[AimbatStation]: ...


@overload
def get_stations_in_event(
    session: Session, event_id: UUID, as_json: Literal[True]
) -> list[dict[str, Any]]: ...


def get_stations_in_event(
    session: Session, event_id: UUID, as_json: bool = False
) -> Sequence[AimbatStation] | list[dict[str, Any]]:
    """Get the stations for a particular event.

    Args:
        session: Database session.
        event_id: ID of the event to get stations for.
        as_json: Whether to return the result as JSON.

    Returns: Stations in event.
    """
    logger.debug(f"Getting stations for event: {event_id}.")

    event = session.get(AimbatEvent, event_id)
    if event is None:
        raise NoResultFound(f"Unable to find event with {event_id=}")

    statement = (
        select(AimbatStation)
        .distinct()
        .join(AimbatSeismogram)
        .where(AimbatSeismogram.event_id == event.id)
        .options(
            selectinload(rel(AimbatStation.seismograms)).selectinload(
                rel(AimbatSeismogram.parameters)
            ),
            selectinload(rel(AimbatStation.seismograms)).selectinload(
                rel(AimbatSeismogram.quality)
            ),
            selectinload(rel(AimbatStation.seismograms)).selectinload(
                rel(AimbatSeismogram.event)
            ),
        )
    )

    logger.debug(f"Executing query: {statement}")
    results = session.exec(statement).all()

    if not as_json:
        return results

    adapter: TypeAdapter[Sequence[AimbatStation]] = TypeAdapter(Sequence[AimbatStation])

    return adapter.dump_python(results, mode="json")


def get_station_iccs_ccs(
    session: Session, station_id: UUID
) -> tuple[float | None, ...]:
    """Get ICCS cross-correlation coefficients for all seismograms of a station across all events.

    Args:
        session: Database session.
        station_id: ID of the station.

    Returns: Tuple of ICCS CC values, one per seismogram (None if not yet computed).
    """
    logger.debug(f"Getting ICCS CCs for {station_id=}.")

    statement = (
        select(AimbatSeismogramQuality.iccs_cc)
        .join(AimbatSeismogram)
        .where(AimbatSeismogram.station_id == station_id)
    )

    return tuple(session.exec(statement).all())


def get_station_quality(session: Session, station_id: UUID) -> SeismogramQualityStats:
    """Get aggregated quality statistics for a station.

    Args:
        session: Database session.
        station_id: UUID of the station.

    Returns:
        Aggregated seismogram quality statistics.

    Raises:
        NoResultFound: If no station with the given ID is found.
    """
    logger.debug(f"Getting quality stats for station {station_id}.")

    station = session.exec(
        select(AimbatStation)
        .where(AimbatStation.id == station_id)
        .options(
            selectinload(rel(AimbatStation.seismograms)).selectinload(
                rel(AimbatSeismogram.quality)
            ),
        )
    ).one_or_none()

    if station is None:
        raise NoResultFound(f"No AimbatStation found with id: {station_id}.")

    return SeismogramQualityStats.from_station(station)


def dump_station_table(
    session: Session,
    from_read_model: bool = False,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Create a JSON serialisable dict from the AimbatStation table data.

    Args:
        session: Database session.
        from_read_model: Whether to dump from the read model (True) or the ORM model.
        by_alias: Whether to use serialization aliases for the field names in the output.
        by_title: Whether to use titles for the field names in the output (only
            applicable when from_read_model is True). Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event ID to filter seismograms by (if none is provided,
            seismograms for all events are dumped).

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
        ValueError: If `by_title` is True but `from_read_model` is False.
    """

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    if not from_read_model and by_title:
        raise ValueError("'by_title' is only supported when 'from_read_model' is True.")

    logger.debug("Dumping AIMBAT station table to json.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    if event_id is not None:
        statement = (
            select(AimbatStation)
            .join(AimbatSeismogram)
            .where(AimbatSeismogram.event_id == event_id)
            .distinct()
        )
    else:
        statement = select(AimbatStation)

    statement = statement.options(
        selectinload(rel(AimbatStation.seismograms)).selectinload(
            rel(AimbatSeismogram.quality)
        ),
        selectinload(rel(AimbatStation.seismograms)).selectinload(
            rel(AimbatSeismogram.parameters)
        ),
        selectinload(rel(AimbatStation.seismograms)).selectinload(
            rel(AimbatSeismogram.event)
        ),
    )

    stations = session.exec(statement).all()

    if from_read_model:
        read_stations = [
            AimbatStationRead.from_station(
                station=s,
                session=session,
            )
            for s in stations
        ]
        read_adapter: TypeAdapter[Sequence[AimbatStationRead]] = TypeAdapter(
            Sequence[AimbatStationRead]
        )
        data = read_adapter.dump_python(
            read_stations, exclude=exclude, by_alias=by_alias, mode="json"
        )

        if by_title:
            title_map = get_title_map(AimbatStationRead)
            return [{title_map.get(k, k): v for k, v in row.items()} for row in data]

        return data

    adapter: TypeAdapter[Sequence[AimbatStation]] = TypeAdapter(Sequence[AimbatStation])
    return adapter.dump_python(
        stations, mode="json", by_alias=by_alias, exclude=exclude
    )


def dump_station_quality_table(
    session: Session,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    station_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Dump station quality statistics to json.

    Args:
        session: Database session.
        by_alias: Whether to use serialization aliases for the field names.
        by_title: Whether to use the field title metadata for the field names.
            Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        station_id: Station ID to filter by (if none is provided, quality for
            all stations is dumped).

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """

    logger.debug("Dumping AIMBAT station quality table to json.")

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    exclude = (exclude or set()) | {"event_id", "snapshot_id"}
    exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    statement = select(AimbatStation).options(
        selectinload(rel(AimbatStation.seismograms)).selectinload(
            rel(AimbatSeismogram.quality)
        ),
    )
    if station_id is not None:
        statement = statement.where(AimbatStation.id == station_id)

    stations = session.exec(statement).all()
    stats = [SeismogramQualityStats.from_station(s) for s in stations]

    adapter: TypeAdapter[Sequence[SeismogramQualityStats]] = TypeAdapter(
        Sequence[SeismogramQualityStats]
    )
    data = adapter.dump_python(stats, mode="json", exclude=exclude, by_alias=by_alias)

    if by_title:
        title_map = get_title_map(SeismogramQualityStats)
        return [{title_map.get(k, k): v for k, v in row.items()} for row in data]

    return data
