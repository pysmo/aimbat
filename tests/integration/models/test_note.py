"""Integration tests for the AimbatNote model's single-parent constraint and core note functions."""

import uuid
from datetime import timezone

import pytest
from pandas import Timestamp
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from aimbat.core import get_note_content, save_note
from aimbat.models import AimbatEvent, AimbatEventParameters, AimbatNote, AimbatStation


def _make_station(session: Session) -> AimbatStation:
    sta = AimbatStation(
        name="AAK",
        network="II",
        location="00",
        channel="BHZ",
        latitude=42.63,
        longitude=74.49,
    )
    session.add(sta)
    session.flush()
    return sta


def _make_event(session: Session) -> AimbatEvent:
    ev = AimbatEvent(
        time=Timestamp("2010-02-27T06:34:14", tz=timezone.utc),
        latitude=-36.12,
        longitude=-72.90,
    )
    session.add(ev)
    session.flush()
    session.add(AimbatEventParameters(event=ev))
    session.flush()
    return ev


class TestAimbatNoteAtMostOneParent:
    """AimbatNote must have at most one FK set."""

    def test_note_with_no_parent_is_valid(self, patched_session: Session) -> None:
        note = AimbatNote.model_validate({"content": "orphan note"})
        patched_session.add(note)
        patched_session.commit()

    def test_note_with_event_parent_is_valid(self, patched_session: Session) -> None:
        ev = _make_event(patched_session)
        note = AimbatNote.model_validate({"content": "event note", "event_id": ev.id})
        patched_session.add(note)
        patched_session.commit()

    def test_note_with_station_parent_is_valid(self, patched_session: Session) -> None:
        sta = _make_station(patched_session)
        note = AimbatNote.model_validate(
            {"content": "station note", "station_id": sta.id}
        )
        patched_session.add(note)
        patched_session.commit()

    def test_model_validator_rejects_two_parents(self) -> None:
        """Pydantic model_validator raises when two FK fields are set."""

        with pytest.raises(ValidationError, match="At most one"):
            AimbatNote.model_validate(
                {
                    "content": "bad note",
                    "event_id": uuid.uuid4(),
                    "station_id": uuid.uuid4(),
                }
            )

    def test_db_constraint_rejects_two_parents(self, patched_session: Session) -> None:
        """DB check constraint rejects a row with two FK fields set."""

        ev_id = uuid.uuid4()
        sta_id = uuid.uuid4()

        # Bypass the model_validator by constructing via __init__ (SQLModel skips
        # Pydantic validation on __init__ for table models) to confirm the DB
        # constraint fires independently.
        note = AimbatNote(content="bypass note", event_id=ev_id, station_id=sta_id)
        patched_session.add(note)
        with pytest.raises(IntegrityError):
            patched_session.flush()


class TestNoteCore:
    """Tests for get_note_content and save_note at the core layer."""

    def test_get_note_content_returns_empty_string_when_no_note_exists(
        self, patched_session: Session
    ) -> None:
        """Verifies that get_note_content returns an empty string when no note exists.

        Args:
            patched_session: The database session.
        """
        result = get_note_content(patched_session, "event", uuid.uuid4())
        assert result == ""

    def test_save_note_creates_note_when_none_exists(
        self, patched_session: Session
    ) -> None:
        """Verifies that save_note creates a new note record when one does not yet exist.

        Args:
            patched_session: The database session.
        """
        ev = _make_event(patched_session)
        assert get_note_content(patched_session, "event", ev.id) == ""

        save_note(patched_session, "event", ev.id, "initial content")

        assert get_note_content(patched_session, "event", ev.id) == "initial content"

    def test_save_note_updates_existing_note(self, patched_session: Session) -> None:
        """Verifies that save_note updates the content of an existing note.

        Args:
            patched_session: The database session.
        """
        ev = _make_event(patched_session)
        save_note(patched_session, "event", ev.id, "first version")
        save_note(patched_session, "event", ev.id, "second version")

        assert get_note_content(patched_session, "event", ev.id) == "second version"
