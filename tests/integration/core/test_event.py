"""Integration tests for event management functions in aimbat.core."""

import json
import uuid
import pytest
from unittest.mock import patch
from aimbat.core import set_active_event, set_active_event_by_id, get_active_event
from aimbat.core._event import (
    delete_event,
    delete_event_by_id,
    get_completed_events,
    get_events_using_station,
    get_event_parameter,
    set_event_parameter,
    dump_event_table_to_json,
    dump_event_parameter_table_to_json,
    print_event_table,
    print_event_parameter_table,
)
from aimbat._types import EventParameter
from aimbat.models import AimbatEvent, AimbatStation
from pandas import Timedelta
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound


@pytest.fixture
def session(loaded_session: Session) -> Session:
    """Provides a session with multi-event data and an active event pre-loaded.

    Args:
        loaded_session: A SQLModel Session with data populated.

    Returns:
        The database session.
    """
    return loaded_session


# ===================================================================
# Active event
# ===================================================================


class TestActiveEvent:
    """Tests for retrieving and switching the active event."""

    def test_get(self, session: Session) -> None:
        """Verifies that `get_active_event` returns the event marked as active in the DB.

        Args:
            session (Session): The database session.
        """
        active_event = session.exec(
            select(AimbatEvent).where(AimbatEvent.active == 1)
        ).one()
        assert active_event == get_active_event(session)

    def test_switch(self, session: Session) -> None:
        """Verifies switching the active event using an event object.

        Args:
            session (Session): The database session.
        """
        active_event = get_active_event(session)
        assert active_event is not None, "expected an active event in the test data"

        all_events = list(session.exec(select(AimbatEvent)).all())
        assert len(all_events) > 1, "expected multiple events in the test data"

        all_events.remove(active_event)
        new_active_event = all_events.pop()
        assert (
            new_active_event != active_event
        ), "expected a different event to switch to"

        set_active_event(session, new_active_event)
        assert get_active_event(session) == new_active_event

    def test_switch_by_id(self, session: Session) -> None:
        """Verifies switching the active event using an event ID.

        Args:
            session (Session): The database session.
        """
        active_event = get_active_event(session)
        event_ids = list(session.exec(select(AimbatEvent.id)).all())

        event_ids.remove(active_event.id)
        new_active_event_id = event_ids.pop()
        assert (
            new_active_event_id != active_event.id
        ), "expected a different event id to switch to"

        set_active_event_by_id(session, new_active_event_id)

        assert (
            get_active_event(session).id == new_active_event_id
        ), "expected the active event to switch to the new event by id"

    def test_switch_by_id_invalid(self, session: Session) -> None:
        """Verifies that switching the active event using an invalid event ID raises an error."""

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
            set_active_event_by_id(session, uuid.uuid4())

    def test_set_same_event_does_not_clear_cache(self, session: Session) -> None:
        """Verifies that re-activating the already-active event does not clear the cache.

        Args:
            session: The database session.
        """
        active_event = get_active_event(session)

        with patch("aimbat.core._active_event.clear_seismogram_cache") as mock_clear:
            set_active_event(session, active_event)
            mock_clear.assert_not_called()

    def test_set_different_event_clears_cache(self, session: Session) -> None:
        """Verifies that switching to a different event clears the cache.

        Args:
            session: The database session.
        """
        active_event = get_active_event(session)
        other_event = next(
            e
            for e in session.exec(select(AimbatEvent)).all()
            if e.id != active_event.id
        )

        with patch("aimbat.core._active_event.clear_seismogram_cache") as mock_clear:
            set_active_event(session, other_event)
            mock_clear.assert_called_once()

    def test_get_active_event_no_active(self, session: Session) -> None:
        """Verifies that `get_active_event` returns None if no event is marked as active.

        Args:
            session (Session): The database session.
        """
        active_event = get_active_event(session)
        assert active_event is not None, "expected an active event in the test data"
        active_event.active = None
        assert (
            session.exec(select(AimbatEvent).where(AimbatEvent.active == 1)).first()
            is None
        ), "expected no active event in the database after deactivating"

        with pytest.raises(NoResultFound):
            get_active_event(session)


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
        non_active = next(e for e in events if not e.active)

        delete_event(session, non_active)

        remaining = session.exec(select(AimbatEvent)).all()
        assert len(remaining) == count_before - 1
        assert non_active not in remaining

    def test_delete_event_by_id(self, session: Session) -> None:
        """Verifies that an event is removed from the database when deleted by ID.

        Args:
            session: The database session.
        """
        events = session.exec(select(AimbatEvent)).all()
        count_before = len(events)
        non_active = next(e for e in events if not e.active)

        delete_event_by_id(session, non_active.id)

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
    """Tests for reading parameter values from the active event."""

    def test_get_timedelta_parameter(self, session: Session) -> None:
        """Verifies that a Timedelta parameter is returned as a Timedelta.

        Args:
            session: The database session.
        """
        value = get_event_parameter(session, EventParameter.WINDOW_PRE)
        assert isinstance(value, Timedelta)

    def test_get_float_parameter(self, session: Session) -> None:
        """Verifies that a float parameter is returned as a float.

        Args:
            session: The database session.
        """
        value = get_event_parameter(session, EventParameter.MIN_CCNORM)
        assert isinstance(value, float)

    def test_get_bool_parameter(self, session: Session) -> None:
        """Verifies that a bool parameter is returned as a bool.

        Args:
            session: The database session.
        """
        value = get_event_parameter(session, EventParameter.COMPLETED)
        assert isinstance(value, bool)


class TestSetEventParameter:
    """Tests for writing parameter values to the active event."""

    def test_set_timedelta_parameter(self, session: Session) -> None:
        """Verifies that a Timedelta parameter is persisted correctly.

        Args:
            session: The database session.
        """
        new_value = Timedelta(seconds=20)
        set_event_parameter(session, EventParameter.WINDOW_POST, new_value)
        assert get_event_parameter(session, EventParameter.WINDOW_POST) == new_value

    def test_set_float_parameter(self, session: Session) -> None:
        """Verifies that a float parameter is persisted correctly.

        Args:
            session: The database session.
        """
        new_value = 0.75
        set_event_parameter(session, EventParameter.MIN_CCNORM, new_value)
        assert get_event_parameter(session, EventParameter.MIN_CCNORM) == new_value

    def test_set_bool_parameter(self, session: Session) -> None:
        """Verifies that a bool parameter is persisted correctly.

        Args:
            session: The database session.
        """
        set_event_parameter(session, EventParameter.COMPLETED, True)
        assert get_event_parameter(session, EventParameter.COMPLETED) is True


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
        assert "active" in result[0]


class TestDumpEventParameterTableToJson:
    """Tests for serialising the event parameter table to JSON."""

    def test_active_event_as_string(self, session: Session) -> None:
        """Verifies that a JSON string of the active event parameters is returned.

        Args:
            session: The database session.
        """
        result = dump_event_parameter_table_to_json(
            session, all_events=False, as_string=True
        )
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "min_ccnorm" in parsed
        assert "window_pre" in parsed
        assert "window_post" in parsed

    def test_active_event_as_dict(self, session: Session) -> None:
        """Verifies that a dict of the active event parameters is returned.

        Args:
            session: The database session.
        """
        result = dump_event_parameter_table_to_json(
            session, all_events=False, as_string=False
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


# ===================================================================
# Print tables
# ===================================================================


class TestPrintEventTable:
    """Tests for printing the event table."""

    def test_print_short(self, session: Session, capsys: pytest.CaptureFixture) -> None:
        """Verifies that print_event_table produces output with short=True.

        Args:
            session: The database session.
            capsys: The pytest capsys fixture.
        """
        print_event_table(session, short=True)
        assert len(capsys.readouterr().out) > 0

    def test_print_long(self, session: Session, capsys: pytest.CaptureFixture) -> None:
        """Verifies that print_event_table produces output with short=False.

        Args:
            session: The database session.
            capsys: The pytest capsys fixture.
        """
        print_event_table(session, short=False)
        assert len(capsys.readouterr().out) > 0


class TestPrintEventParameterTable:
    """Tests for printing the event parameter table."""

    def test_print_active_event(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        """Verifies that print_event_parameter_table produces output for the active event.

        Args:
            session: The database session.
            capsys: The pytest capsys fixture.
        """
        print_event_parameter_table(session, short=False, all_events=False)
        assert len(capsys.readouterr().out) > 0

    def test_print_all_events(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        """Verifies that print_event_parameter_table produces output for all events.

        Args:
            session: The database session.
            capsys: The pytest capsys fixture.
        """
        print_event_parameter_table(session, short=False, all_events=True)
        assert len(capsys.readouterr().out) > 0
