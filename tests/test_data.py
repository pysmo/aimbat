from __future__ import annotations
from pysmo.classes import SAC
from sqlmodel import select, Session
from typing import TYPE_CHECKING
from pathlib import Path
import pytest
import numpy as np


if TYPE_CHECKING:
    from pytest import CaptureFixture
    from sqlalchemy.engine import Engine
    from typing import Any
    from collections.abc import Generator


@pytest.mark.dependency(depends=["create_project"], scope="session")
class TestLibDataBase:
    @pytest.fixture
    def session(
        self, test_db_with_project: tuple[Path, str, Engine, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_project[3]


class TestLibData(TestLibDataBase):
    @pytest.mark.dependency(name="add_sac_file_to_project")
    def test_add_sac_file_to_project(
        self, sac_file_good: Path, session: Session
    ) -> None:
        from aimbat.lib.data import add_files_to_project, SeismogramFileType, AimbatFile

        add_files_to_project(
            session,
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        seismogram_filename = session.exec(select(AimbatFile.filename)).one()
        assert seismogram_filename == str(sac_file_good)

        # do this a second time to see that nothing changes
        add_files_to_project(
            session,
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        seismogram_filename = session.exec(select(AimbatFile.filename)).one()
        assert seismogram_filename == str(sac_file_good)

    @pytest.mark.dependency(depends=["add_sac_file_to_project"])
    def test_compare_aimbat_seis_to_sac_seis(
        self, sac_file_good: Path, session: Session, sac_instance_good: SAC
    ) -> None:
        from aimbat.lib.data import add_files_to_project, SeismogramFileType
        from aimbat.lib.models import AimbatSeismogram

        add_files_to_project(
            session,
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        sac_seismogram = sac_instance_good.seismogram
        aimbat_seismogram = session.exec(select(AimbatSeismogram)).one()

        assert np.array_equal(aimbat_seismogram.data, sac_seismogram.data)
        assert aimbat_seismogram.delta == sac_seismogram.delta
        assert aimbat_seismogram.begin_time == sac_seismogram.begin_time
        assert len(aimbat_seismogram) == len(sac_seismogram)

    @pytest.mark.dependency(depends=["add_sac_file_to_project"])
    def test_compare_aimbat_station_to_sac_station(
        self, sac_file_good: Path, session: Session, sac_instance_good: SAC
    ) -> None:
        from aimbat.lib.data import add_files_to_project, SeismogramFileType
        from aimbat.lib.models import AimbatStation, AimbatSeismogram

        add_files_to_project(
            session,
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        sac_station = sac_instance_good.station
        aimbat_seismogram = session.exec(select(AimbatSeismogram)).one()
        aimbat_station = session.exec(select(AimbatStation)).one()
        assert aimbat_seismogram.station == aimbat_station
        assert aimbat_station.name == sac_instance_good.kstnm
        assert aimbat_station.latitude == sac_station.latitude
        assert aimbat_station.longitude == sac_station.longitude
        assert aimbat_station.elevation == sac_station.elevation

    @pytest.mark.dependency(depends=["add_sac_file_to_project"])
    def test_compare_aimbat_event_to_sac_event(
        self, sac_file_good: Path, session: Session, sac_instance_good: SAC
    ) -> None:
        from aimbat.lib.data import add_files_to_project, SeismogramFileType
        from aimbat.lib.models import AimbatEvent, AimbatSeismogram

        add_files_to_project(
            session,
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        sac_event = sac_instance_good.event
        aimbat_seismogram = session.exec(select(AimbatSeismogram)).one()
        aimbat_event = session.exec(select(AimbatEvent)).one()
        assert aimbat_seismogram.event == aimbat_event
        assert aimbat_event.latitude == sac_event.latitude
        assert aimbat_event.longitude == sac_event.longitude
        assert aimbat_event.depth == sac_event.depth

    @pytest.mark.dependency(depends=["add_sac_file_to_project"])
    def test_file_uuid_dict_reversed(
        self, sac_file_good: Path, session: Session
    ) -> None:
        from aimbat.lib.data import (
            file_uuid_dict_reversed,
            add_files_to_project,
            SeismogramFileType,
        )
        import uuid

        add_files_to_project(
            session,
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        for k, v in file_uuid_dict_reversed(session).items():
            assert isinstance(k, uuid.UUID)
            assert isinstance(v, str)

    @pytest.mark.dependency(depends=["add_sac_file_to_project"])
    def test_get_data_for_active_event(
        self, sac_file_good: Path, session: Session
    ) -> None:
        from aimbat.lib.data import (
            add_files_to_project,
            SeismogramFileType,
            get_data_for_active_event,
            AimbatFile,
        )

        add_files_to_project(
            session,
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        for file in get_data_for_active_event(session):
            assert isinstance(file, AimbatFile)

    @pytest.mark.dependency(depends=["add_sac_file_to_project"])
    def test_print_data_table(
        self,
        sac_file_good: Path,
        session: Session,
        capsys: CaptureFixture,
    ) -> None:
        from aimbat.lib.data import (
            add_files_to_project,
            SeismogramFileType,
            print_data_table,
        )
        from aimbat.lib.models import AimbatEvent

        add_files_to_project(
            session,
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        aimbat_event = session.exec(select(AimbatEvent)).one()
        aimbat_event.active = True
        session.add(aimbat_event)
        session.commit()

        print_data_table(session, format=True)
        captured = capsys.readouterr()
        assert "AIMBAT data for event 2011-09-15 19:31:04" in captured.out
        print_data_table(session, format=False)
        captured = capsys.readouterr()
        assert "AIMBAT data for event 2011-09-15 19:31:04.080000+00:00" in captured.out
        print_data_table(session, format=True, all_events=True)
        captured = capsys.readouterr()
        # assert "AIMBAT is awesome" in captured.out
        assert "AIMBAT data for all events" in captured.out
        print_data_table(session, format=False, all_events=True)
        captured = capsys.readouterr()
        assert "AIMBAT data for all events" in captured.out


class TestCliDataBase:
    @pytest.fixture
    def db_url(
        self, test_db_with_project: tuple[Path, str, Engine, Session]
    ) -> Generator[str, Any, Any]:
        yield test_db_with_project[1]


class TestCliData(TestCliDataBase):
    def test_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["data"])
        assert "Usage" in capsys.readouterr().out

    @pytest.mark.dependency(depends=["add_sac_file_to_project"])
    def test_cli_data_add(
        self,
        db_url: str,
        sac_file_good: Path,
        capsys: CaptureFixture,
    ) -> None:
        from aimbat.app import app

        sac_file_good_as_string = str(sac_file_good)

        app(["data", "add", "--db-url", db_url, sac_file_good_as_string])

        app(["data", "list", "--all", "--db-url", db_url])
        assert sac_file_good_as_string in capsys.readouterr().out
