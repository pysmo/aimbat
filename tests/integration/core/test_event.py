"""Integration tests for event management functions in aimbat.core."""

import uuid

import pytest
from pandas import Timedelta
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat._types import EventParameter
from aimbat.core import (
    delete_event,
    dump_event_parameter_table,
    dump_event_table,
    get_completed_events,
    get_events_using_station,
    set_event_parameter,
)
from aimbat.models import AimbatEvent, AimbatStation

# ===================================================================
# Default event
# ===================================================================


class TestDeleteEvent:
    """Tests for deleting events from the database."""

    def test_delete_event(self, loaded_session: Session) -> None:
        """Verifies that an event is removed from the database after deletion.

        Args:
            loaded_session: The database session.
        """
        events = loaded_session.exec(select(AimbatEvent)).all()
        count_before = len(events)
        to_delete = events[0]

        delete_event(loaded_session, to_delete.id)

        remaining = loaded_session.exec(select(AimbatEvent)).all()
        assert len(remaining) == count_before - 1
        assert to_delete not in remaining

    def test_delete_event_by_id_not_found(self, loaded_session: Session) -> None:
        """Verifies that deleting a non-existent event ID raises NoResultFound.

        Args:
            loaded_session: The database session.
        """
        with pytest.raises(NoResultFound):
            delete_event(loaded_session, uuid.uuid4())


# ===================================================================
# Query events
# ===================================================================


class TestGetCompletedEvents:
    """Tests for retrieving events marked as completed."""

    def test_no_completed_events(self, loaded_session: Session) -> None:
        """Verifies that no events are returned when none are marked as completed.

        Args:
            loaded_session: The database session.
        """
        completed = get_completed_events(loaded_session)
        assert len(completed) == 0

    def test_get_completed_events(self, loaded_session: Session) -> None:
        """Verifies that only events marked as completed are returned.

        Args:
            loaded_session: The database session.
        """
        events = loaded_session.exec(select(AimbatEvent)).all()
        target = events[0]
        target.parameters.completed = True
        loaded_session.add(target)
        loaded_session.commit()

        completed = get_completed_events(loaded_session)
        assert len(completed) == 1
        assert target in completed


class TestGetEventsUsingStation:
    """Tests for retrieving events associated with a particular station."""

    def test_get_events_using_station(self, loaded_session: Session) -> None:
        """Verifies that events linked to a station are returned.

        Args:
            loaded_session: The database session.
        """
        station = loaded_session.exec(select(AimbatStation)).first()
        assert station is not None

        events = get_events_using_station(loaded_session, station.id)
        assert len(events) > 0
        for event in events:
            station_ids = [s.station_id for s in event.seismograms]
            assert station.id in station_ids

    def test_get_events_using_station_no_match(self, loaded_session: Session) -> None:
        """Verifies that an empty sequence is returned for a station with no events.

        Args:
            loaded_session: The database session.
        """
        orphan = AimbatStation(
            network="XX",
            name="NONE",
            location="00",
            channel="BHZ",
            latitude=0.0,
            longitude=0.0,
        )
        loaded_session.add(orphan)
        loaded_session.commit()

        events = get_events_using_station(loaded_session, orphan.id)
        assert len(events) == 0


# ===================================================================
# Event parameters
# ===================================================================


class TestSetEventParameter:
    """Tests for writing parameter values to the default event."""

    def test_set_timedelta_parameter(self, loaded_session: Session) -> None:
        """Verifies that a Timedelta parameter is persisted correctly.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        new_value = Timedelta(seconds=20)
        set_event_parameter(
            loaded_session, event.id, EventParameter.WINDOW_POST, new_value
        )
        assert event.parameters.window_post == new_value

    def test_set_float_parameter(self, loaded_session: Session) -> None:
        """Verifies that a float parameter is persisted correctly.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        new_value = 0.75
        set_event_parameter(loaded_session, event.id, EventParameter.MIN_CC, new_value)
        assert event.parameters.min_cc == new_value

    def test_set_bool_parameter(self, loaded_session: Session) -> None:
        """Verifies that a bool parameter is persisted correctly.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        set_event_parameter(loaded_session, event.id, EventParameter.COMPLETED, True)
        assert event.parameters.completed is True

    def test_set_parameter_with_validate_iccs(self, loaded_session: Session) -> None:
        """Verifies that validate_iccs=True triggers ICCS validation.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        # Test valid change
        new_value = Timedelta(seconds=1.5)
        set_event_parameter(
            loaded_session,
            event.id,
            EventParameter.WINDOW_POST,
            new_value,
            validate_iccs=True,
        )
        assert event.parameters.window_post == new_value

        # Test invalid change (e.g., window that would result in no data)
        # Very large window might fail construction if it exceeds data bounds
        with pytest.raises(ValueError, match="ICCS validation failed"):
            set_event_parameter(
                loaded_session,
                event.id,
                EventParameter.WINDOW_POST,
                Timedelta(seconds=10000),
                validate_iccs=True,
            )


# ===================================================================
# JSON serialisation
# ===================================================================


class TestDumpEventTableToJson:
    """Tests for serialising the event table to JSON."""

    def test_default_returns_string(self, loaded_session: Session) -> None:
        """Verifies that a JSON string is returned by default.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_table(loaded_session)
        assert isinstance(result, str)
        assert '"id":' in result

    def test_from_read_model_returns_list(self, loaded_session: Session) -> None:
        """Verifies that a list of dicts is returned when from_read_model=True.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_table(loaded_session, from_read_model=True)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "id" in result[0]
        assert "last_modified" in result[0]

    def test_from_read_model_with_alias(self, loaded_session: Session) -> None:
        """Verifies that aliases are used when by_alias=True.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_table(loaded_session, from_read_model=True, by_alias=True)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "lastModified" in result[0]
        assert "last_modified" not in result[0]


class TestDumpEventParameterTableToJson:
    """Tests for serialising the event parameter table to JSON."""

    def test_all_events_as_list(self, loaded_session: Session) -> None:
        """Verifies that a list of dicts of all event parameters is returned.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_parameter_table(loaded_session)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "min_cc" in result[0]
        assert "window_pre" in result[0]
        assert "window_post" in result[0]

    def test_all_events_with_alias(self, loaded_session: Session) -> None:
        """Verifies that aliases are used when by_alias=True.

        Args:
            loaded_session: The database session.
        """
        result = dump_event_parameter_table(loaded_session, by_alias=True)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "minCc" in result[0]
        assert "windowPre" in result[0]
        assert "windowPost" in result[0]
        assert "min_cc" not in result[0]
