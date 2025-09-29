from aimbat.lib.models import AimbatStation
from aimbat.app import app
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from importlib import reload
from typing import Any
from collections.abc import Generator
import aimbat.lib.station as station
import random
import pytest
import json


class TestStationBase:
    @pytest.fixture(autouse=True)
    def session(
        self, fixture_session_with_active_event: Session
    ) -> Generator[Session, Any, Any]:
        reload(station)
        yield fixture_session_with_active_event


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

        app(["station", "delete", str(id)])
        session.flush()
        assert (
            session.exec(
                select(AimbatStation).where(AimbatStation.id == id)
            ).one_or_none()
            is None
        )

    def test_cli_delete_station_by_id_with_wrong_id(self) -> None:
        import uuid

        id = uuid.uuid4()

        with pytest.raises(NoResultFound):
            app(["station", "delete", str(id)])

    def test_cli_delete_station_by_string(self, session: Session) -> None:
        station = random.choice(list(session.exec(select(AimbatStation))))
        id = station.id

        app(["station", "delete", str(id)[:5]])
        session.flush()
        assert (
            session.exec(
                select(AimbatStation).where(AimbatStation.id == id)
            ).one_or_none()
            is None
        )


class TestLibStation(TestStationBase):
    def test_sac_data(self, capsys: pytest.CaptureFixture) -> None:
        station.print_station_table(short=False)
        assert "AIMBAT stations for event" in capsys.readouterr().out

        station.print_station_table(short=True)
        assert "ID (shortened)" in capsys.readouterr().out

        station.print_station_table(short=False, all_events=True)
        assert "AIMBAT stations for all events" in capsys.readouterr().out

        station.print_station_table(short=True, all_events=True)
        assert "# Seismograms" in capsys.readouterr().out


class TestCliStation(TestStationBase):
    def test_usage(self, capsys: pytest.CaptureFixture) -> None:
        app(["station"])
        assert "Usage" in capsys.readouterr().out

    def test_station_list(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        app(["station", "list", "--all"])
        assert "# Seismograms" in capsys.readouterr().out


class TestDumpStation(TestStationBase):
    def test_lib_dump_data(self, capsys: pytest.CaptureFixture) -> None:
        station.dump_station_table()
        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatStation(**i)

    def test_cli_dump_data(self, capsys: pytest.CaptureFixture) -> None:
        app(["station", "dump"])
        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatStation(**i)
