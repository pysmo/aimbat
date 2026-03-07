"""Integration tests for station management functions in aimbat.core._station."""

import json
import uuid

import pytest
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat.core import get_default_event
from aimbat.core._station import (
    delete_station,
    delete_station_by_id,
    dump_station_table_to_json,
    dump_station_table_with_counts,
    get_stations_in_event,
    get_stations_with_event_and_seismogram_count,
)
from aimbat.models import AimbatStation


@pytest.fixture
def session(loaded_session: Session) -> Session:
    """Provides a session with multi-event data and an default event pre-loaded.

    Args:
        loaded_session: A SQLModel Session with data populated.

    Returns:
        The database session.
    """
    return loaded_session


@pytest.fixture
def station(session: Session) -> AimbatStation:
    """Provides the first station associated with the default event.

    Args:
        session: The database session.

    Returns:
        The first AimbatStation in the default event.
    """
    default_event = get_default_event(session)
    assert default_event is not None
    return default_event.seismograms[0].station


class TestDeleteStation:
    """Tests for deleting stations from the database."""

    def test_delete_station(self, session: Session, station: AimbatStation) -> None:
        """Verifies that a station is removed from the database.

        Args:
            session: The database session.
            station: The station to delete.
        """
        station_id = station.id
        delete_station(session, station)
        assert session.get(AimbatStation, station_id) is None, (
            "Station should be absent after deletion"
        )

    def test_delete_station_by_id(
        self, session: Session, station: AimbatStation
    ) -> None:
        """Verifies that a station is removed when deleted by ID.

        Args:
            session: The database session.
            station: The station whose ID is used for deletion.
        """
        station_id = station.id
        delete_station_by_id(session, station_id)
        assert session.get(AimbatStation, station_id) is None, (
            "Station should be absent after deletion by ID"
        )

    def test_delete_station_by_id_not_found(self, session: Session) -> None:
        """Verifies that deleting a non-existent station ID raises NoResultFound.

        Args:
            session: The database session.
        """
        with pytest.raises(NoResultFound):
            delete_station_by_id(session, uuid.uuid4())


class TestGetStationsInDefaultEvent:
    """Tests for retrieving stations in the default event."""

    def test_returns_stations(self, session: Session) -> None:
        """Verifies that stations for the default event are returned.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        stations = get_stations_in_event(session, default_event, as_json=False)
        assert len(stations) > 0, "Expected at least one station for the default event"

    def test_returns_aimbat_station_instances(self, session: Session) -> None:
        """Verifies that all returned items are AimbatStation instances.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        stations = get_stations_in_event(session, default_event, as_json=False)
        assert all(isinstance(s, AimbatStation) for s in stations), (
            "All returned items should be AimbatStation instances"
        )

    def test_as_json_returns_list_of_dicts(self, session: Session) -> None:
        """Verifies that as_json=True returns a list of dicts.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        result = get_stations_in_event(session, default_event, as_json=True)
        assert isinstance(result, list), "Expected a list when as_json=True"
        assert all(isinstance(item, dict) for item in result), (
            "Each element should be a dict when as_json=True"
        )

    def test_as_json_count_matches_objects(self, session: Session) -> None:
        """Verifies that as_json=True and as_json=False return the same number of stations.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        objects = get_stations_in_event(session, default_event, as_json=False)
        json_list = get_stations_in_event(session, default_event, as_json=True)
        assert len(objects) == len(json_list), (
            "Object and JSON representations should have the same length"
        )

    def test_stations_belong_to_default_event(self, session: Session) -> None:
        """Verifies that the returned stations are associated with the default event.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        default_station_ids = {s.station_id for s in default_event.seismograms}
        stations = get_stations_in_event(session, default_event, as_json=False)
        returned_ids = {s.id for s in stations}
        assert returned_ids == default_station_ids, (
            "Returned station IDs should match those linked to the default event"
        )


class TestGetStationsInEvent:
    """Tests for retrieving stations in a specific event."""

    def test_returns_stations_for_event(self, session: Session) -> None:
        """Verifies that stations for the given event are returned.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        stations = get_stations_in_event(session, default_event)
        assert len(stations) > 0, "Expected at least one station for the given event"

    def test_returns_aimbat_station_instances(self, session: Session) -> None:
        """Verifies that all returned items are AimbatStation instances.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        stations = get_stations_in_event(session, default_event)
        assert all(isinstance(s, AimbatStation) for s in stations), (
            "All returned items should be AimbatStation instances"
        )

    def test_station_ids_match_event_seismograms(self, session: Session) -> None:
        """Verifies that station IDs match those linked to the event's seismograms.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        expected_ids = {s.station_id for s in default_event.seismograms}
        returned_ids = {s.id for s in get_stations_in_event(session, default_event)}
        assert returned_ids == expected_ids, (
            "Station IDs should match those linked to the event's seismograms"
        )


class TestGetStationsWithEventSeismogramCount:
    """Tests for retrieving stations with associated seismogram and event counts."""

    def test_returns_all_stations(self, session: Session) -> None:
        """Verifies that all stations in the database are returned.

        Args:
            session: The database session.
        """
        all_stations = session.exec(select(AimbatStation)).all()
        results = get_stations_with_event_and_seismogram_count(session)
        assert len(results) == len(all_stations), (
            "Expected one row per station in the database"
        )

    def test_returns_tuples_with_counts(self, session: Session) -> None:
        """Verifies that each result is a tuple of (AimbatStation, int, int).

        Args:
            session: The database session.
        """
        results = get_stations_with_event_and_seismogram_count(session)
        for row in results:
            station, seismogram_count, event_count = row
            assert isinstance(station, AimbatStation), (
                "First element should be an AimbatStation"
            )
            assert isinstance(seismogram_count, int), (
                "Second element should be an int (seismogram count)"
            )
            assert isinstance(event_count, int), (
                "Third element should be an int (event count)"
            )

    def test_counts_are_non_negative(self, session: Session) -> None:
        """Verifies that all seismogram and event counts are non-negative.

        Args:
            session: The database session.
        """
        results = get_stations_with_event_and_seismogram_count(session)
        for _, seismogram_count, event_count in results:
            assert seismogram_count >= 0, "Seismogram count should be non-negative"
            assert event_count >= 0, "Event count should be non-negative"

    def test_as_json_returns_list_of_dicts(self, session: Session) -> None:
        """Verifies that as_json=True returns a list of dicts with count fields.

        Args:
            session: The database session.
        """
        results = dump_station_table_with_counts(session)
        assert isinstance(results, list), "Expected a list when as_json=True"
        for item in results:
            assert isinstance(item, dict), "Each element should be a dict"
            assert "seismogram_count" in item, "Dict should contain 'seismogram_count'"
            assert "event_count" in item, "Dict should contain 'event_count'"

    def test_as_json_count_matches_objects(self, session: Session) -> None:
        """Verifies that both return modes yield the same number of rows.

        Args:
            session: The database session.
        """
        objects = get_stations_with_event_and_seismogram_count(session)
        json_list = dump_station_table_with_counts(session)
        assert len(objects) == len(json_list), (
            "Object and JSON representations should have the same number of rows"
        )


class TestDumpStationTableToJson:
    """Tests for dumping the full station table to JSON."""

    def test_returns_valid_json_string(self, session: Session) -> None:
        """Verifies that the result is a valid JSON string.

        Args:
            session: The database session.
        """
        result = dump_station_table_to_json(session)
        assert isinstance(result, str), "Expected a string result"
        parsed = json.loads(result)
        assert isinstance(parsed, list), "Parsed JSON should be a list"

    def test_entry_count_matches_database(self, session: Session) -> None:
        """Verifies that the JSON contains one entry per station in the database.

        Args:
            session: The database session.
        """
        all_stations = session.exec(select(AimbatStation)).all()
        result = json.loads(dump_station_table_to_json(session))
        assert len(result) == len(all_stations), (
            "JSON entry count should match station count in the database"
        )

    def test_entries_contain_id_field(self, session: Session) -> None:
        """Verifies that each entry in the JSON has an 'id' field.

        Args:
            session: The database session.
        """
        result = json.loads(dump_station_table_to_json(session))
        for entry in result:
            assert "id" in entry, "Each station entry should have an 'id' field"
