"""Actions that modify stations."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Engine

from aimbat import core
from aimbat.models import AimbatStation

from ._session import open_session, require_ids

__all__ = ["delete_stations"]


def delete_stations(
    station_ids: Sequence[UUID], *, engine: Engine | None = None
) -> None:
    """Delete stations, together with every seismogram recorded at them.

    Args:
        station_ids: IDs of the stations to delete.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not a station. Nothing is deleted.
    """
    with open_session(engine) as session:
        for station_id in require_ids(session, AimbatStation, station_ids):
            core.delete_station(session, station_id)
        session.commit()
