from __future__ import annotations
from pydantic_core import ValidationError
from sqlmodel import Session, select
from pathlib import Path
from typing import TYPE_CHECKING
import pytest
import random


if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any
    from sqlalchemy.engine import Engine
    from aimbat.lib.models import AimbatEvent
    from pytest import CaptureFixture


class TestLibEventBase:
    @pytest.fixture
    def session(
        self, test_db_with_data: tuple[Path, str, Engine, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_data[3]

    def get_random_event(self, session: Session) -> AimbatEvent:
        from aimbat.lib.event import AimbatEvent

        events = session.exec(select(AimbatEvent)).all()
        return random.choice(events)

    def activate_random_event(self, session: Session) -> AimbatEvent:
        from aimbat.lib.event import set_active_event

        event = self.get_random_event(session)
        set_active_event(session, event)
        return event


class TestLibEvent(TestLibEventBase):
    def test_get_active_event_when_none_is_active(self, session: Session) -> None:
        from aimbat.lib.event import get_active_event, AimbatEvent

        events = session.exec(select(AimbatEvent)).all()
        assert all(e.active is None for e in events)

        with pytest.raises(RuntimeError):
            get_active_event(session)

    def test_set_active_event(self, session: Session) -> None:
        from aimbat.lib.event import set_active_event, AimbatEvent

        events = session.exec(select(AimbatEvent)).all()
        assert all(e.active is None for e in events)
        event = random.choice(events)

        set_active_event(session, event)
        assert event.active is True

    def test_change_active_event(self, session: Session) -> None:
        from aimbat.lib.event import set_active_event, AimbatEvent

        events = list(session.exec(select(AimbatEvent)).all())
        assert all(e.active is None for e in events)
        random.shuffle(events)

        first_active_event = events.pop()
        second_active_event = events.pop()

        set_active_event(session, first_active_event)
        assert first_active_event.active is True

        set_active_event(session, second_active_event)
        assert first_active_event.active is None
        assert second_active_event.active is True

    def test_set_active_event_by_id(self, session: Session) -> None:
        from aimbat.lib.event import set_active_event_by_id, AimbatEvent
        import uuid

        events = list(session.exec(select(AimbatEvent)).all())
        assert all(e.active is None for e in events)
        event = random.choice(events)

        set_active_event_by_id(session, event.id)
        assert event.active is True

        with pytest.raises(ValueError):
            set_active_event_by_id(session, uuid.uuid4())

    def test_get_completed_events(self, session: Session) -> None:
        from aimbat.lib.event import get_completed_events, AimbatEvent

        assert len(get_completed_events(session)) == 0
        events = list(session.exec(select(AimbatEvent)).all())
        event = random.choice(events)
        event.parameters.completed = True
        session.commit()
        assert len(get_completed_events(session)) == 1
        assert get_completed_events(session)[0].id == event.id

    def test_get_event_parameter(self, session: Session) -> None:
        from aimbat.lib.event import (
            get_event_parameter,
            EventParameter,
        )

        event = self.activate_random_event(session)

        assert (
            get_event_parameter(session, EventParameter.COMPLETED)
            == event.parameters.completed
        )
        assert (
            get_event_parameter(session, EventParameter.MIN_CCNORM)
            == event.parameters.min_ccnorm
        )
        assert (
            get_event_parameter(session, EventParameter.WINDOW_POST)
            == event.parameters.window_post
        )
        assert (
            get_event_parameter(session, EventParameter.WINDOW_PRE)
            == event.parameters.window_pre
        )

    def test_set_event_parameter(self, session: Session) -> None:
        from aimbat.lib.event import (
            set_event_parameter,
            get_event_parameter,
            EventParameter,
        )

        _ = self.activate_random_event(session)

        assert get_event_parameter(session, EventParameter.COMPLETED) is False
        set_event_parameter(session, EventParameter.COMPLETED, True)
        assert get_event_parameter(session, EventParameter.COMPLETED) is True
        with pytest.raises(ValidationError):
            set_event_parameter(session, EventParameter.COMPLETED, "foo")

    def test_print_event_table(self, session: Session, capsys: CaptureFixture) -> None:
        from aimbat.lib.event import print_event_table

        _ = self.activate_random_event(session)

        print_event_table(session)
        captured = capsys.readouterr()
        assert "AIMBAT Events" in captured.out
        assert "2012-01-12 19:31:04" in captured.out
        print_event_table(session, format=False)
        captured = capsys.readouterr()
        assert "AIMBAT Events" in captured.out
        assert "2011-09-15 19:31:04.080000+00:00" in captured.out


class TestCliEventBase:
    @pytest.fixture
    def db_url(
        self, test_db_with_data: tuple[Path, str, Engine, Session]
    ) -> Generator[str, Any, Any]:
        yield test_db_with_data[1]


class TestCliEvent(TestCliEventBase, TestLibEventBase):
    def test_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["event"])
        assert "Usage" in capsys.readouterr().out

    def test_event_activate(self, db_url: str, session: Session) -> None:
        from aimbat.app import app

        event = self.get_random_event(session)
        assert event.active is None

        app(["event", "activate", str(event.id), "--db-url", db_url])

        session.refresh(event)
        assert event.active is True

    def test_event_activate_with_str_id(self, db_url: str, session: Session) -> None:
        from aimbat.app import app

        event = self.get_random_event(session)
        assert event.active is None
        short_uuid = str(event.id)[:6]

        app(["event", "activate", short_uuid, "--db-url", db_url])

        session.refresh(event)
        assert event.active is True

    def test_get_event_parameter(
        self, db_url: str, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.app import app

        _ = self.activate_random_event(session)
        app(["event", "get", "completed", "--db-url", db_url])
        assert "False" in capsys.readouterr().out

        app(["event", "get", "window_post", "--db-url", db_url])
        assert "15.0s" in capsys.readouterr().out

    def test_set_event_parameter(
        self, db_url: str, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.app import app

        _ = self.activate_random_event(session)
        app(["event", "get", "completed", "--db-url", db_url])
        assert "False" in capsys.readouterr().out
        app(["event", "set", "completed", "True", "--db-url", db_url])
        app(["event", "get", "completed", "--db-url", db_url])
        assert "True" in capsys.readouterr().out

    def test_event_list(
        self,
        db_url: str,
        capsys: CaptureFixture,
    ) -> None:
        from aimbat.app import app

        app(["event", "list", "--db-url", db_url])
        assert "AIMBAT Events" in capsys.readouterr().out
