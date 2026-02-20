from aimbat import settings
from aimbat.utils import get_active_event
from aimbat.models import AimbatEvent, AimbatStation, AimbatSeismogram
from aimbat.aimbat_types import EventParameter
from pydantic_core import ValidationError
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from typing import Any
from collections.abc import Generator, Sequence
import aimbat.core._event as event
import pytest
import random
import json


class TestEventBase:
    @pytest.fixture
    def session(
        self, fixture_session_with_data: Session
    ) -> Generator[Session, Any, Any]:
        yield fixture_session_with_data

    def get_random_station(self, session: Session) -> AimbatStation:
        stations = session.exec(select(AimbatStation)).all()
        return random.choice(stations)

    def get_random_event(self, session: Session) -> AimbatEvent:
        events = session.exec(select(AimbatEvent)).all()
        return random.choice(events)

    def activate_random_event(self, session: Session) -> AimbatEvent:
        random_event = self.get_random_event(session)
        event.set_active_event(session, random_event)
        return random_event


class TestDeleteEvent(TestEventBase):
    def test_lib_delete_event_by_id(self, session: Session) -> None:
        aimbat_event = self.get_random_event(session)
        id = aimbat_event.id
        event.delete_event_by_id(session, id)
        assert (
            session.exec(select(AimbatEvent).where(AimbatEvent.id == id)).one_or_none()
            is None
        )

    def test_cli_delete_event_by_id(self, session: Session) -> None:
        from aimbat.app import app

        aimbat_event = self.get_random_event(session)
        id = aimbat_event.id

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "delete", str(id)])

        assert excinfo.value.code == 0

        session.flush()
        assert (
            session.exec(select(AimbatEvent).where(AimbatEvent.id == id)).one_or_none()
            is None
        )

    def test_cli_delete_event_by_id_with_wrong_id(self, session: Session) -> None:
        from aimbat.app import app
        from uuid import uuid4

        id = uuid4()

        with pytest.raises(NoResultFound):
            app(["event", "delete", str(id)])

    def test_cli_delete_event_by_string(self, session: Session) -> None:
        from aimbat.app import app

        aimbat_event = random.choice(list(session.exec(select(AimbatEvent))))
        id = aimbat_event.id

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "delete", str(id)[:5]])

        assert excinfo.value.code == 0

        session.flush()
        assert (
            session.exec(select(AimbatEvent).where(AimbatEvent.id == id)).one_or_none()
            is None
        )


class TestGetActiveEvent(TestEventBase):
    def test_get_active_event_when_none_is_active(self, session: Session) -> None:
        events = session.exec(select(AimbatEvent)).all()
        assert all(e.active is None for e in events)

        with pytest.raises(NoResultFound):
            get_active_event(session)


class TestSetActiveEvent(TestEventBase):
    def test_lib_set_active_event(self, session: Session) -> None:
        events = session.exec(select(AimbatEvent)).all()
        assert all(e.active is None for e in events)
        aimbat_event = random.choice(events)

        event.set_active_event(session, aimbat_event)
        assert aimbat_event.active is True

    def test_lib_change_active_event(self, session: Session) -> None:
        events = list(session.exec(select(AimbatEvent)).all())
        assert all(e.active is None for e in events)
        random.shuffle(events)

        first_active_event = events.pop()
        second_active_event = events.pop()

        event.set_active_event(session, first_active_event)
        assert first_active_event.active is True

        event.set_active_event(session, second_active_event)
        assert first_active_event.active is None
        assert second_active_event.active is True

    def test_lib_set_active_event_by_id(self, session: Session) -> None:
        import uuid

        events = list(session.exec(select(AimbatEvent)).all())
        assert all(e.active is None for e in events)
        aimbat_event = random.choice(events)

        event.set_active_event_by_id(session, aimbat_event.id)
        assert aimbat_event.active is True

        with pytest.raises(ValueError):
            event.set_active_event_by_id(session, uuid.uuid4())

    def test_cli_event_activate(self, session: Session) -> None:
        from aimbat.app import app

        event = self.get_random_event(session)
        assert event.active is None

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "activate", str(event.id)])

        assert excinfo.value.code == 0

        session.refresh(event)
        assert event.active is True

    def test_cli_event_activate_with_str_id(self, session: Session) -> None:
        from aimbat.app import app

        event = self.get_random_event(session)
        assert event.active is None
        short_uuid = str(event.id)[:6]

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "activate", short_uuid])

        assert excinfo.value.code == 0

        session.refresh(event)
        assert event.active is True


class TestGetCompletedEvents(TestEventBase):
    def test_get_completed_events(self, session: Session) -> None:
        assert len(event.get_completed_events(session)) == 0
        events = list(session.exec(select(AimbatEvent)).all())
        aimbat_event = random.choice(events)
        aimbat_event.parameters.completed = True
        session.commit()
        assert len(event.get_completed_events(session)) == 1
        assert event.get_completed_events(session)[0].id == aimbat_event.id


class TestGetEvents(TestEventBase):
    @pytest.fixture
    def all_events(
        self, session: Session
    ) -> Generator[Sequence[AimbatEvent], Any, Any]:
        from aimbat.models import AimbatEvent

        yield session.exec(select(AimbatEvent)).all()

    @pytest.fixture
    def all_seismograms(
        self, session: Session
    ) -> Generator[Sequence[AimbatSeismogram], Any, Any]:
        from aimbat.models import AimbatSeismogram

        yield session.exec(select(AimbatSeismogram)).all()

    def test_lib_get_events_using_station(
        self, session: Session, all_seismograms: Sequence[AimbatSeismogram]
    ) -> None:
        station = self.get_random_station(session)

        event_set1 = set(
            s.event.id for s in all_seismograms if s.station.id == station.id
        )
        event_set2 = set(e.id for e in event.get_events_using_station(session, station))

        assert event_set1 == event_set2


class TestGetEventParameter(TestEventBase):
    def test_lib_get_event_parameter(self, session: Session) -> None:
        aimbat_event = self.activate_random_event(session)

        assert (
            event.get_event_parameter(session, EventParameter.COMPLETED)
            == aimbat_event.parameters.completed
        )
        assert (
            event.get_event_parameter(session, EventParameter.MIN_CCNORM)
            == aimbat_event.parameters.min_ccnorm
        )
        assert (
            event.get_event_parameter(session, EventParameter.WINDOW_POST)
            == aimbat_event.parameters.window_post
        )
        assert (
            event.get_event_parameter(session, EventParameter.WINDOW_PRE)
            == aimbat_event.parameters.window_pre
        )

    def test_lib_set_event_parameter(self, session: Session) -> None:
        _ = self.activate_random_event(session)

        assert event.get_event_parameter(session, EventParameter.COMPLETED) is False
        event.set_event_parameter(session, EventParameter.COMPLETED, True)
        assert event.get_event_parameter(session, EventParameter.COMPLETED) is True
        with pytest.raises(ValidationError):
            event.set_event_parameter(session, EventParameter.COMPLETED, "foo")

    def test_lib_print_event_table(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        _ = self.activate_random_event(session)

        event.print_event_table(session)
        captured = capsys.readouterr()
        assert "AIMBAT Events" in captured.out
        assert "2012-01-12 19:31:04" in captured.out
        event.print_event_table(session, short=False)
        captured = capsys.readouterr()
        assert "AIMBAT Events" in captured.out
        assert "2011-09-15 19:31:04.080000+00:00" in captured.out

    def test_cli_get_event_parameter(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        from aimbat.app import app

        _ = self.activate_random_event(session)

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "get", "completed"])

        assert excinfo.value.code == 0
        assert "False" in capsys.readouterr().out

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "get", "window_post"])

        assert excinfo.value.code == 0
        assert f"{settings.window_post.total_seconds()}s" in capsys.readouterr().out


class TestCliEvent(TestEventBase):
    def test_cli_usage(self, capsys: pytest.CaptureFixture) -> None:
        from aimbat.app import app

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "--help"])

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        assert "Usage" in captured.out

    def test_cli_set_event_parameter(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        from aimbat.app import app

        _ = self.activate_random_event(session)

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "get", "completed"])

        assert excinfo.value.code == 0
        assert "False" in capsys.readouterr().out

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "set", "completed", "True"])

        assert excinfo.value.code == 0

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "get", "completed"])

        assert excinfo.value.code == 0
        assert "True" in capsys.readouterr().out

    def test_cli_event_list(
        self,
        session: Session,
        capsys: pytest.CaptureFixture,
    ) -> None:
        from aimbat.app import app

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "list"])

        assert excinfo.value.code == 0
        assert "AIMBAT Events" in capsys.readouterr().out


class TestEventDump(TestEventBase):
    def test_lib_dump_event(
        self, fixture_session_with_data: Session, capsys: pytest.CaptureFixture
    ) -> None:
        event.dump_event_table(fixture_session_with_data)
        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatEvent(**i)

    def test_cli_dump_data(
        self, fixture_session_with_data: Session, capsys: pytest.CaptureFixture
    ) -> None:
        from aimbat.app import app

        with pytest.raises(SystemExit) as excinfo:
            app(["event", "dump"])

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatEvent(**i)
