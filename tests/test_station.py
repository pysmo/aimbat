from __future__ import annotations
from aimbat.lib.models import AimbatStation
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from importlib import reload
from typing import TYPE_CHECKING
import aimbat.lib.station as station
import random
import pytest

if TYPE_CHECKING:
    from typing import Any
    from pytest import CaptureFixture
    from collections.abc import Generator
    from pathlib import Path


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
    def test_station_uuid_dict_reversed(self, session: Session) -> None:
        from aimbat.lib.station import station_uuid_dict_reversed
        import uuid

        for k, v in station_uuid_dict_reversed(session).items():
            assert isinstance(k, uuid.UUID)
            assert isinstance(v, str)

    def test_sac_data(self, capsys: CaptureFixture) -> None:
        station.print_station_table(format=False)
        assert "AIMBAT stations for event" in capsys.readouterr().out

        station.print_station_table(format=True)
        assert "id (shortened)" in capsys.readouterr().out

        station.print_station_table(format=False, all_events=True)
        assert "AIMBAT stations for all events" in capsys.readouterr().out

        station.print_station_table(format=True, all_events=True)
        assert "# Seismograms" in capsys.readouterr().out


class TestCliStation(TestStationBase):
    def test_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["station"])
        assert "Usage" in capsys.readouterr().out

    def test_station_list(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["station", "list", "--all"])
        assert "# Seismograms" in capsys.readouterr().out
