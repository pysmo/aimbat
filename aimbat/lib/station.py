from aimbat.logger import logger
from aimbat.lib.db import engine
from aimbat.lib.common import uuid_shortener
from aimbat.lib.utils.json import dump_to_json
from aimbat.lib.models import AimbatStation, AimbatSeismogram, AimbatEvent
from aimbat.cli.styling import make_table, TABLE_COLOURS
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from rich.console import Console
from collections.abc import Sequence
import aimbat.lib.event as event
import uuid


def delete_station_by_id(session: Session, station_id: uuid.UUID) -> None:
    """Delete an AimbatStation from the database by ID.

    Parameters:
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

    Parameters:
        session: Database session.
        station: Station to delete.
    """

    logger.info(f"Deleting station {station.id}.")

    session.delete(station)
    session.commit()


def get_stations_in_event(
    session: Session, event: AimbatEvent
) -> Sequence[AimbatStation]:
    """Get the stations for a particular event.

    Parameters:
        session: Database session.
        event: Event to return stations for.

    Returns: Stations in event.
    """

    logger.info(f"Getting stations for event: {event.id}.")

    select_stations = (
        select(AimbatStation)
        .join(AimbatSeismogram)
        .join(AimbatEvent)
        .where(AimbatEvent.id == event.id)
    )

    stations = session.exec(select_stations).all()

    logger.debug(f"Found {len(stations)}.")

    return stations


def print_station_table(short: bool, all_events: bool = False) -> None:
    """Prints a pretty table with AIMBAT stations.

    Parameters:
        short: Shorten and format the output to be more human-readable.
        all_events: Print stations for all events.
    """

    logger.info("Printing station table.")

    title = "AIMBAT stations for all events"
    aimbat_stations = None

    with Session(engine) as session:
        if all_events:
            logger.debug("Selecting all AIMBAT stations.")
            aimbat_stations = session.exec(select(AimbatStation)).all()
        else:
            logger.debug("Selecting AIMBAT stations for active event.")
            active_event = event.get_active_event(session)
            aimbat_stations = get_stations_in_event(session, active_event)
            if short:
                title = f"AIMBAT stations for event {active_event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_shortener(session, active_event)})"
            else:
                title = f"AIMBAT stations for event {active_event.time} (ID={active_event.id})"
        logger.debug("Found {len(aimbat_stations)} stations for the table.")

        table = make_table(title=title)

        if short:
            table.add_column(
                "id (shortened)", justify="center", style=TABLE_COLOURS.id, no_wrap=True
            )
        else:
            table.add_column(
                "id", justify="center", style=TABLE_COLOURS.id, no_wrap=True
            )
        table.add_column(
            "Name & Network", justify="center", style=TABLE_COLOURS.mine, no_wrap=True
        )
        table.add_column("Latitude", justify="center", style=TABLE_COLOURS.mine)
        table.add_column("Longitude", justify="center", style=TABLE_COLOURS.mine)
        table.add_column("Elevation", justify="center", style=TABLE_COLOURS.mine)
        if all_events:
            table.add_column(
                "# Seismograms", justify="center", style=TABLE_COLOURS.linked
            )
            table.add_column("# Events", justify="center", style=TABLE_COLOURS.linked)

        for aimbat_station in aimbat_stations:
            logger.debug(f"Adding {aimbat_station.name} to the table.")
            row = [
                (
                    uuid_shortener(session, aimbat_station)
                    if short
                    else str(aimbat_station.id)
                ),
                f"{aimbat_station.name} - {aimbat_station.network}",
                (
                    f"{aimbat_station.latitude:.3f}"
                    if short
                    else str(aimbat_station.latitude)
                ),
                (
                    f"{aimbat_station.longitude:.3f}"
                    if short
                    else str(aimbat_station.longitude)
                ),
                (
                    f"{aimbat_station.elevation:.0f}"
                    if short
                    else str(aimbat_station.elevation)
                ),
            ]
            if all_events:
                row.extend(
                    [
                        str(len(aimbat_station.seismograms)),
                        str(len({i.event_id for i in aimbat_station.seismograms})),
                    ]
                )
            table.add_row(*row)

    console = Console()
    console.print(table)


def dump_station_table() -> None:
    """Dump the table data to json."""

    logger.info("Dumping AIMBAT station table to json.")

    with Session(engine) as session:
        aimbat_stations = session.exec(select(AimbatStation)).all()
        dump_to_json(aimbat_stations)
