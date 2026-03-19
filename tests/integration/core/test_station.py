"""Integration tests for station management functions in aimbat.core._station."""

import uuid

import pytest
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat.core._station import (
    delete_station,
    dump_station_table,
    get_stations_in_event,
)
from aimbat.models import AimbatEvent, AimbatStation


@pytest.fixture
def station(loaded_session: Session) -> AimbatStation:
    """Provides the first station from the database.

    Args:
        loaded_session: The database session.

    Returns:
        The first AimbatStation in the database.
    """
    station = loaded_session.exec(select(AimbatStation)).first()
    assert station is not None
    return station


class TestDeleteStation:
    """Tests for deleting stations from the database."""

    def test_delete_station(
        self, loaded_session: Session, station: AimbatStation
    ) -> None:
        """Verifies that a station is removed from the database.

        Args:
            loaded_session: The database session.
            station: The station to delete.
        """
        station_id = station.id
        delete_station(loaded_session, station.id)
        assert loaded_session.get(AimbatStation, station_id) is None, (
            "Station should be absent after deletion"
        )

    def test_delete_station_id_not_found(self, loaded_session: Session) -> None:
        """Verifies that deleting a non-existent station ID raises NoResultFound.

        Args:
            loaded_session: The database session.
        """
        with pytest.raises(NoResultFound):
            delete_station(loaded_session, uuid.uuid4())


class TestGetStationsInEvent:
    """Tests for retrieving stations in a specific event."""

    def test_returns_stations_for_event(self, loaded_session: Session) -> None:
        """Verifies that stations for the given event are returned.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        stations = get_stations_in_event(loaded_session, event.id)
        assert len(stations) > 0, "Expected at least one station for the given event"

    def test_returns_aimbat_station_instances(self, loaded_session: Session) -> None:
        """Verifies that all returned items are AimbatStation instances.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        stations = get_stations_in_event(loaded_session, event.id)
        assert all(isinstance(s, AimbatStation) for s in stations), (
            "All returned items should be AimbatStation instances"
        )

    def test_as_json_returns_list_of_dicts(self, loaded_session: Session) -> None:
        """Verifies that as_json=True returns a list of dicts.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        result = get_stations_in_event(loaded_session, event.id, as_json=True)
        assert isinstance(result, list), "Expected a list when as_json=True"
        assert all(isinstance(item, dict) for item in result), (
            "Each element should be a dict when as_json=True"
        )

    def test_as_json_count_matches_objects(self, loaded_session: Session) -> None:
        """Verifies that as_json=True and as_json=False return the same number of stations.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        objects = get_stations_in_event(loaded_session, event.id, as_json=False)
        json_list = get_stations_in_event(loaded_session, event.id, as_json=True)
        assert len(objects) == len(json_list), (
            "Object and JSON representations should have the same length"
        )

    def test_stations_belong_to_event(self, loaded_session: Session) -> None:
        """Verifies that the returned stations are associated with the event.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        station_ids = {s.station_id for s in event.seismograms}
        stations = get_stations_in_event(loaded_session, event.id, as_json=False)
        returned_ids = {s.id for s in stations}
        assert returned_ids == station_ids, (
            "Returned station IDs should match those linked to the event"
        )


class TestDumpStationTableToJson:
    """Tests for dumping the full station table to JSON."""

    def test_entry_count_matches_database(self, loaded_session: Session) -> None:
        """Verifies that the JSON contains one entry per station in the database.

        Args:
            loaded_session: The database session.
        """
        all_stations = loaded_session.exec(select(AimbatStation)).all()
        result = dump_station_table(loaded_session)
        assert len(result) == len(all_stations), (
            "JSON entry count should match station count in the database"
        )

    def test_entries_contain_id_field(self, loaded_session: Session) -> None:
        """Verifies that each entry in the JSON has an 'id' field.

        Args:
            loaded_session: The database session.
        """
        result = dump_station_table(loaded_session)
        for entry in result:
            assert "id" in entry, "Each station entry should have an 'id' field"
