"""Unit tests for aimbat.utils._uuid."""

import uuid
from collections.abc import Generator

import pandas as pd
import pytest
from sqlmodel import Session, SQLModel, create_engine

from aimbat.models import AimbatEvent
from aimbat.utils._uuid import string_to_uuid, uuid_shortener


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    """Provide an in-memory SQLite session with all tables created.

    Yields:
        Session: The database session.
    """
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def _make_event(uid: uuid.UUID, offset_seconds: int = 0) -> AimbatEvent:
    """Helper to create an AimbatEvent with a specific UUID and time offset.

    Args:
        uid (uuid.UUID): The UUID for the event.
        offset_seconds (int): Time offset in seconds (default: 0).

    Returns:
        AimbatEvent: The created event.
    """
    return AimbatEvent(
        id=uid,
        time=pd.Timestamp("2000-01-01") + pd.Timedelta(seconds=offset_seconds),
        latitude=0.0,
        longitude=0.0,
        depth=0.0,
    )


class TestStringToUuid:
    """Tests for the string_to_uuid function."""

    def test_resolves_full_uuid(self, session: Session) -> None:
        """Verifies resolving a full UUID string.

        Args:
            session (Session): Database session.
        """
        uid = uuid.uuid4()
        session.add(_make_event(uid))
        session.commit()
        result = string_to_uuid(session, str(uid), AimbatEvent)
        assert result == uid

    def test_resolves_short_prefix(self, session: Session) -> None:
        """Verifies resolving a UUID from a short prefix.

        Args:
            session (Session): Database session.
        """
        uid = uuid.uuid4()
        session.add(_make_event(uid))
        session.commit()
        prefix = str(uid).replace("-", "")[:6]
        result = string_to_uuid(session, prefix, AimbatEvent)
        assert result == uid

    def test_raises_on_no_match(self, session: Session) -> None:
        """Verifies that ValueError is raised when no match is found.

        Args:
            session (Session): Database session.
        """
        with pytest.raises(ValueError, match="Unable to find"):
            string_to_uuid(session, "000000", AimbatEvent)

    def test_raises_on_ambiguous_match(self, session: Session) -> None:
        """Verifies that ValueError is raised when multiple matches are found.

        Args:
            session (Session): Database session.
        """
        # Force two UUIDs that share the same prefix by crafting them manually.
        uid1 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
        uid2 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000002")
        session.add(_make_event(uid1, offset_seconds=0))
        session.add(_make_event(uid2, offset_seconds=1))
        session.commit()
        with pytest.raises(ValueError, match="more than one"):
            string_to_uuid(session, "aaaaaaaa", AimbatEvent)

    def test_custom_error_message(self, session: Session) -> None:
        """Verifies that a custom error message is used when provided.

        Args:
            session (Session): Database session.
        """
        with pytest.raises(ValueError, match="custom error"):
            string_to_uuid(session, "000000", AimbatEvent, custom_error="custom error")

    def test_ignores_dashes_in_input(self, session: Session) -> None:
        """Verifies that dashes in the input string are ignored.

        Args:
            session (Session): Database session.
        """
        uid = uuid.UUID("abcdef12-1234-4000-8000-000000000001")
        session.add(_make_event(uid))
        session.commit()
        result = string_to_uuid(session, "abcdef12-1234", AimbatEvent)
        assert result == uid


class TestUuidShortener:
    """Tests for the uuid_shortener function."""

    def test_returns_unique_prefix_for_single_entry(self, session: Session) -> None:
        """Verifies getting a unique prefix for a single event.

        Args:
            session (Session): Database session.
        """
        uid = uuid.uuid4()
        event = _make_event(uid)
        session.add(event)
        session.commit()
        short = uuid_shortener(session, event)
        assert str(uid).startswith(short)

    def test_prefix_is_shortest_unique(self, session: Session) -> None:
        """Verifies that the returned prefix is the shortest possible unique prefix.

        Args:
            session (Session): Database session.
        """
        uid1 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
        uid2 = uuid.UUID("bbbbbbbb-0000-4000-8000-000000000002")
        e1 = _make_event(uid1, offset_seconds=0)
        e2 = _make_event(uid2, offset_seconds=1)
        session.add(e1)
        session.add(e2)
        session.commit()
        short1 = uuid_shortener(session, e1)
        short2 = uuid_shortener(session, e2)
        # Each prefix must uniquely identify its UUID.
        assert str(uid1).startswith(short1)
        assert str(uid2).startswith(short2)
        assert not str(uid2).startswith(short1)
        assert not str(uid1).startswith(short2)

    def test_disambiguates_shared_prefix(self, session: Session) -> None:
        """Verifies disambiguation when prefixes are shared.

        Args:
            session (Session): Database session.
        """
        uid1 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
        uid2 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000002")
        e1 = _make_event(uid1, offset_seconds=0)
        e2 = _make_event(uid2, offset_seconds=1)
        session.add(e1)
        session.add(e2)
        session.commit()
        short1 = uuid_shortener(session, e1)
        short2 = uuid_shortener(session, e2)
        assert short1 != short2
        assert str(uid1).startswith(short1)
        assert str(uid2).startswith(short2)

    def test_class_form_with_str_uuid(self, session: Session) -> None:
        """Verifies calling with class and string UUID.

        Args:
            session (Session): Database session.
        """
        uid = uuid.uuid4()
        session.add(_make_event(uid))
        session.commit()
        short = uuid_shortener(session, AimbatEvent, str_uuid=str(uid))
        assert str(uid).startswith(short)

    def test_class_form_requires_str_uuid(self, session: Session) -> None:
        """Verifies that str_uuid is required when calling with a class.

        Args:
            session (Session): Database session.
        """
        with pytest.raises(ValueError, match="str_uuid must be provided"):
            uuid_shortener(session, AimbatEvent)

    def test_raises_if_id_not_in_table(self, session: Session) -> None:
        """Verifies that ValueError is raised if the ID is not in the table.

        Args:
            session (Session): Database session.
        """
        uid = uuid.uuid4()
        # Do not add the event to the session.
        with pytest.raises(ValueError, match="not found in table"):
            uuid_shortener(session, AimbatEvent, str_uuid=str(uid))

    def test_min_length_respected(self, session: Session) -> None:
        """Verifies that the minimum length constraint is respected.

        Args:
            session (Session): Database session.
        """
        uid = uuid.uuid4()
        session.add(_make_event(uid))
        session.commit()
        event = session.get(AimbatEvent, uid)
        assert event is not None, "expected event to exist in database"
        short = uuid_shortener(session, event, min_length=4)
        # Result must be at least 4 chars (excluding any trailing dash).
        assert len(short.replace("-", "")) >= 4
