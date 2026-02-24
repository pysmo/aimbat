"""Integration tests for managing the active event in the database."""

import pytest
import uuid
from aimbat.core import set_active_event, set_active_event_by_id, get_active_event
from aimbat.models import AimbatEvent
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound

# -----------------------------------------------------------------------------
# Do all tests with the session fixture that has multi_event data pre-loaded
# -----------------------------------------------------------------------------


@pytest.fixture
def session(loaded_session: Session) -> Session:
    """Provides a session with multi_event data pre-loaded.

    Args:
        loaded_session (Session): The session fixture with data.

    Returns:
        Session: The database session.
    """
    return loaded_session


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
