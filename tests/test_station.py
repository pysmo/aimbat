from aimbat.lib.models import AimbatStation
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from importlib import reload
from typing import Any
from collections.abc import Generator
from pathlib import Path
import aimbat.lib.station as station
import random
import pytest
import json


class TestStationBase:
    @pytest.fixture(autouse=True)
    def reload_modules(self, test_db_with_active_event: tuple[Path, Session]) -> None:
        reload(station)

    @pytest.fixture
    def session(
        self, test_db_with_active_event: tuple[Path, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_active_event[1]


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
        from aimbat.app import app

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
        from aimbat.app import app
        from uuid import uuid4

        id = uuid4()

        with pytest.raises(NoResultFound):
            app(["station", "delete", str(id)])

    def test_cli_delete_station_by_string(self, session: Session) -> None:
        from aimbat.app import app

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
        assert "id (shortened)" in capsys.readouterr().out

        station.print_station_table(short=False, all_events=True)
        assert "AIMBAT stations for all events" in capsys.readouterr().out

        station.print_station_table(short=True, all_events=True)
        assert "# Seismograms" in capsys.readouterr().out


class TestCliStation(TestStationBase):
    def test_usage(self, capsys: pytest.CaptureFixture) -> None:
        from aimbat.app import app

        app(["station"])
        assert "Usage" in capsys.readouterr().out

    def test_station_list(self, capsys: pytest.CaptureFixture) -> None:
        from aimbat.app import app

        app(["station", "list", "--all"])
        assert "# Seismograms" in capsys.readouterr().out


class TestDumpStation(TestStationBase):
    def test_lib_dump_data(
        self,
        test_db_with_data: tuple[Path, Session],
        capsys: pytest.CaptureFixture,
    ) -> None:
        reload(station)
        station.dump_station_table()
        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatStation(**i)

    def test_cli_dump_data(
        self,
        test_db_with_data: tuple[Path, Session],
        capsys: pytest.CaptureFixture,
    ) -> None:
        reload(station)
        from aimbat.app import app

        app(["station", "dump"])
        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatStation(**i)
