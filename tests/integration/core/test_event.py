"""Integration tests for event management functions in aimbat.core."""

import json
import uuid
import pytest
from aimbat.core import (
    set_default_event,
    set_default_event_by_id,
    get_default_event,
    delete_event,
    delete_event_by_id,
    get_completed_events,
    get_events_using_station,
    get_event_parameter,
    set_event_parameter,
    dump_event_table_to_json,
    dump_event_parameter_table_to_json,
)
from aimbat._types import EventParameter
from aimbat.models import AimbatEvent, AimbatStation
from pandas import Timedelta
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound


@pytest.fixture
def session(loaded_session: Session) -> Session:
    """Provides a session with multi-event data and a default event pre-loaded.

    Args:
        loaded_session: A SQLModel Session with data populated.

    Returns:
        The database session.
    """
    return loaded_session


# ===================================================================
# Default event
# ===================================================================


class TestDefaultEvent:
    """Tests for retrieving and switching the default event."""

    def test_get(self, session: Session) -> None:
        """Verifies that `get_default_event` returns the event marked as default in the DB.

        Args:
            session (Session): The database session.
        """
        default_event = session.exec(
            select(AimbatEvent).where(AimbatEvent.is_default == 1)
        ).one()
        assert default_event == get_default_event(session)

    def test_switch(self, session: Session) -> None:
        """Verifies switching the default event using an event object.

        Args:
            session (Session): The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None, "expected a default event in the test data"

        all_events = list(session.exec(select(AimbatEvent)).all())
        assert len(all_events) > 1, "expected multiple events in the test data"

        all_events.remove(default_event)
        new_default_event = all_events.pop()
        assert (
            new_default_event != default_event
        ), "expected a different event to switch to"

        set_default_event(session, new_default_event)
        assert get_default_event(session) == new_default_event

    def test_switch_by_id(self, session: Session) -> None:
        """Verifies switching the default event using an event ID.

        Args:
            session (Session): The database session.
        """
        default_event = get_default_event(session)
        event_ids = list(session.exec(select(AimbatEvent.id)).all())

        event_ids.remove(default_event.id)
        new_default_event_id = event_ids.pop()
        assert (
            new_default_event_id != default_event.id
        ), "expected a different event id to switch to"

        set_default_event_by_id(session, new_default_event_id)

        assert (
            get_default_event(session).id == new_default_event_id
        ), "expected the default event to switch to the new event by id"

    def test_switch_by_id_invalid(self, session: Session) -> None:
        """Verifies that switching the default event using an invalid event ID raises an error."""

        new_uuid = uuid.uuid4()
        assert (
            len(
                session.exec(
                    select(AimbatEvent).where(AimbatEvent.id == new_uuid)
                ).all()
            )
            == 0
        ), "expected no event with the generated UUID in the test data"

        with pytest.raises(ValueError):
            set_default_event_by_id(session, uuid.uuid4())

    def test_get_default_event_no_default(self, session: Session) -> None:
        """Verifies that `get_default_event` returns None if no event is marked as default.

        Args:
            session (Session): The database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None, "expected a default event in the test data"
        default_event.is_default = None
        assert (
            session.exec(select(AimbatEvent).where(AimbatEvent.is_default == 1)).first()
            is None
        ), "expected no default event in the database after deactivating"

        with pytest.raises(NoResultFound):
            get_default_event(session)


# ===================================================================
# Delete event
# ===================================================================


class TestDeleteEvent:
    """Tests for deleting events from the database."""

    def test_delete_event(self, session: Session) -> None:
        """Verifies that an event is removed from the database after deletion.

        Args:
            session: The database session.
        """
        events = session.exec(select(AimbatEvent)).all()
        count_before = len(events)
        non_default = next(e for e in events if not e.is_default)

        delete_event(session, non_default)

        remaining = session.exec(select(AimbatEvent)).all()
        assert len(remaining) == count_before - 1
        assert non_default not in remaining

    def test_delete_event_by_id(self, session: Session) -> None:
        """Verifies that an event is removed from the database when deleted by ID.

        Args:
            session: The database session.
        """
        events = session.exec(select(AimbatEvent)).all()
        count_before = len(events)
        non_default = next(e for e in events if not e.is_default)

        delete_event_by_id(session, non_default.id)

        remaining = session.exec(select(AimbatEvent)).all()
        assert len(remaining) == count_before - 1

    def test_delete_event_by_id_not_found(self, session: Session) -> None:
        """Verifies that deleting a non-existent event ID raises NoResultFound.

        Args:
            session: The database session.
        """
        with pytest.raises(NoResultFound):
            delete_event_by_id(session, uuid.uuid4())


# ===================================================================
# Query events
# ===================================================================


class TestGetCompletedEvents:
    """Tests for retrieving events marked as completed."""

    def test_no_completed_events(self, session: Session) -> None:
        """Verifies that no events are returned when none are marked as completed.

        Args:
            session: The database session.
        """
        completed = get_completed_events(session)
        assert len(completed) == 0

    def test_get_completed_events(self, session: Session) -> None:
        """Verifies that only events marked as completed are returned.

        Args:
            session: The database session.
        """
        events = session.exec(select(AimbatEvent)).all()
        target = events[0]
        target.parameters.completed = True
        session.add(target)
        session.commit()

        completed = get_completed_events(session)
        assert len(completed) == 1
        assert target in completed


class TestGetEventsUsingStation:
    """Tests for retrieving events associated with a particular station."""

    def test_get_events_using_station(self, session: Session) -> None:
        """Verifies that events linked to a station are returned.

        Args:
            session: The database session.
        """
        station = session.exec(select(AimbatStation)).first()
        assert station is not None

        events = get_events_using_station(session, station)
        assert len(events) > 0
        for event in events:
            station_ids = [s.station_id for s in event.seismograms]
            assert station.id in station_ids

    def test_get_events_using_station_no_match(self, session: Session) -> None:
        """Verifies that an empty sequence is returned for a station with no events.

        Args:
            session: The database session.
        """
        orphan = AimbatStation(
            network="XX",
            name="NONE",
            location="00",
            channel="BHZ",
            latitude=0.0,
            longitude=0.0,
        )
        session.add(orphan)
        session.commit()

        events = get_events_using_station(session, orphan)
        assert len(events) == 0


# ===================================================================
# Event parameters
# ===================================================================


class TestGetEventParameter:
    """Tests for reading parameter values from the default event."""

    def test_get_timedelta_parameter(self, session: Session) -> None:
        """Verifies that a Timedelta parameter is returned as a Timedelta.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        value = get_event_parameter(session, default_event, EventParameter.WINDOW_PRE)
        assert isinstance(value, Timedelta)

    def test_get_float_parameter(self, session: Session) -> None:
        """Verifies that a float parameter is returned as a float.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        value = get_event_parameter(session, default_event, EventParameter.MIN_CCNORM)
        assert isinstance(value, float)

    def test_get_bool_parameter(self, session: Session) -> None:
        """Verifies that a bool parameter is returned as a bool.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        value = get_event_parameter(session, default_event, EventParameter.COMPLETED)
        assert isinstance(value, bool)


class TestSetEventParameter:
    """Tests for writing parameter values to the default event."""

    def test_set_timedelta_parameter(self, session: Session) -> None:
        """Verifies that a Timedelta parameter is persisted correctly.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        new_value = Timedelta(seconds=20)
        set_event_parameter(
            session, default_event, EventParameter.WINDOW_POST, new_value
        )
        assert (
            get_event_parameter(session, default_event, EventParameter.WINDOW_POST)
            == new_value
        )

    def test_set_float_parameter(self, session: Session) -> None:
        """Verifies that a float parameter is persisted correctly.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        new_value = 0.75
        set_event_parameter(
            session, default_event, EventParameter.MIN_CCNORM, new_value
        )
        assert (
            get_event_parameter(session, default_event, EventParameter.MIN_CCNORM)
            == new_value
        )

    def test_set_bool_parameter(self, session: Session) -> None:
        """Verifies that a bool parameter is persisted correctly.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        set_event_parameter(session, default_event, EventParameter.COMPLETED, True)
        assert (
            get_event_parameter(session, default_event, EventParameter.COMPLETED)
            is True
        )


# ===================================================================
# JSON serialisation
# ===================================================================


class TestDumpEventTableToJson:
    """Tests for serialising the event table to JSON."""

    def test_as_string(self, session: Session) -> None:
        """Verifies that a JSON string is returned when as_string=True.

        Args:
            session: The database session.
        """
        result = dump_event_table_to_json(session, as_string=True)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) > 0

    def test_as_list(self, session: Session) -> None:
        """Verifies that a list of dicts is returned when as_string=False.

        Args:
            session: The database session.
        """
        result = dump_event_table_to_json(session, as_string=False)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "id" in result[0]
        assert "is_default" in result[0]


class TestDumpEventParameterTableToJson:
    """Tests for serialising the event parameter table to JSON."""

    def test_default_event_as_string(self, session: Session) -> None:
        """Verifies that a JSON string of the default event parameters is returned.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        result = dump_event_parameter_table_to_json(
            session, all_events=False, as_string=True, event=default_event
        )
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "min_ccnorm" in parsed
        assert "window_pre" in parsed
        assert "window_post" in parsed

    def test_default_event_as_dict(self, session: Session) -> None:
        """Verifies that a dict of the default event parameters is returned.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        result = dump_event_parameter_table_to_json(
            session, all_events=False, as_string=False, event=default_event
        )
        assert isinstance(result, dict)
        assert "min_ccnorm" in result
        assert "window_pre" in result
        assert "window_post" in result

    def test_all_events_as_string(self, session: Session) -> None:
        """Verifies that a JSON string of all event parameters is returned.

        Args:
            session: The database session.
        """
        result = dump_event_parameter_table_to_json(
            session, all_events=True, as_string=True
        )
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) > 0

    def test_all_events_as_list(self, session: Session) -> None:
        """Verifies that a list of dicts of all event parameters is returned.

        Args:
            session: The database session.
        """
        result = dump_event_parameter_table_to_json(
            session, all_events=True, as_string=False
        )
        assert isinstance(result, list)
        assert len(result) > 0
        assert "min_ccnorm" in result[0]
