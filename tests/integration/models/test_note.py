"""Integration tests for the AimbatNote model's single-parent constraint."""

import uuid
from datetime import timezone

import pytest
from pandas import Timestamp
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

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
