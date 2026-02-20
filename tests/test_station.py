from aimbat.models import AimbatStation
from aimbat.app import app
from sqlmodel import Session, select
from sqlalchemy import Engine
from typing import Any
from collections.abc import Generator
import aimbat.core._station as station
import random
import pytest
import json


class TestStationBase:
    @pytest.fixture(autouse=True)
    def session(
        self, fixture_engine_session_with_active_event: tuple[Engine, Session]
    ) -> Generator[Session, Any, Any]:
        session = fixture_engine_session_with_active_event[1]
        yield session


class TestDeleteStation(TestStationBase):
    def test_lib_delete_station_by_id(self, session: Session) -> None:
        aimbat_station = random.choice(list(session.exec(select(AimbatStation))))
        id = aimbat_station.id
        station.delete_station_by_id(session, id)
        assert (
            session.exec(
                select(AimbatStation).where(AimbatStation.id == id)
            ).one_or_none()
            is None
        )

    def test_cli_delete_station_by_id(self, session: Session) -> None:
        seismogram = random.choice(list(session.exec(select(AimbatStation))))
        id = seismogram.id

        with pytest.raises(SystemExit) as excinfo:
            app(["station", "delete", str(id)])

        assert excinfo.value.code == 0

        session.flush()
        assert (
            session.exec(
                select(AimbatStation).where(AimbatStation.id == id)
            ).one_or_none()
            is None
        )

    def test_cli_delete_station_by_id_with_wrong_id(self) -> None:
        from aimbat import settings

        settings.log_level = "INFO"

        import uuid

        id = uuid.uuid4()

        with pytest.raises(SystemExit) as excinfo:
            app(["station", "delete", str(id)])

        assert excinfo.value.code == 1

    def test_cli_delete_station_by_string(self, session: Session) -> None:
        station = random.choice(list(session.exec(select(AimbatStation))))
        id = station.id

        with pytest.raises(SystemExit) as excinfo:
            app(["station", "delete", str(id)[:5]])

        assert excinfo.value.code == 0

        session.flush()
        assert (
            session.exec(
                select(AimbatStation).where(AimbatStation.id == id)
            ).one_or_none()
            is None
        )


class TestLibStation(TestStationBase):
    def test_sac_data(self, session: Session, capsys: pytest.CaptureFixture) -> None:
        station.print_station_table(session, short=False)
        assert "AIMBAT stations for event" in capsys.readouterr().out

        station.print_station_table(session, short=True)
        assert "ID (shortened)" in capsys.readouterr().out

        station.print_station_table(session, short=False, all_events=True)
        assert "AIMBAT stations for all events" in capsys.readouterr().out

        station.print_station_table(session, short=True, all_events=True)
        assert "# Seismograms" in capsys.readouterr().out


class TestCliStation(TestStationBase):
    def test_cli_usage(self, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(["station", "--help"])

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        assert "Usage" in captured.out

    def test_cli_station_list(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(["station", "list", "--all"])

        assert excinfo.value.code == 0

        captured = capsys.readouterr()

        assert "# Seismograms" in captured.out


class TestDumpStation(TestStationBase):
    def test_lib_dump_data(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        station.dump_station_table(session)
        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatStation(**i)

    def test_cli_dump_data(self, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(["station", "dump"])

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatStation(**i)
