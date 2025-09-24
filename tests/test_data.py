from __future__ import annotations
from pysmo.classes import SAC
from sqlmodel import select, Session
from typing import TYPE_CHECKING
from pathlib import Path
from importlib import reload
from aimbat.lib.typing import SeismogramFileType
import aimbat.lib.data as data
import pytest
import numpy as np


if TYPE_CHECKING:
    from pytest import CaptureFixture


# @pytest.mark.dependency(depends=["create_project"], scope="session")
class TestDataBase:
    @pytest.fixture(autouse=True)
    def reload_modules(self, test_db_with_project: tuple[Path, Session]) -> None:
        reload(data)


class TestDataAdd(TestDataBase):
    def test_lib_add_sac_file_to_project(
        self,
        sac_file_good: Path,
        test_db_with_project: tuple[Path, Session],
    ) -> None:
        data.add_files_to_project(
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        session = test_db_with_project[1]
        seismogram_filename = session.exec(select(data.AimbatFile.filename)).one()
        assert seismogram_filename == str(sac_file_good)

        # do this a second time to see that nothing changes
        data.add_files_to_project(
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        seismogram_filename = session.exec(select(data.AimbatFile.filename)).one()
        assert seismogram_filename == str(sac_file_good)

    def test_cli_data_add(
        self,
        sac_file_good: Path,
        test_db_with_project: tuple[Path, Session],
    ) -> None:
        from aimbat.app import app

        sac_file_good_as_string = str(sac_file_good)

        app(["data", "add", "--no-progress", sac_file_good_as_string])

        session = test_db_with_project[1]
        seismogram_filename = session.exec(select(data.AimbatFile.filename)).one()
        assert seismogram_filename == str(sac_file_good)


class TestDataTable(TestDataBase):
    def test_lib_print_data_table_without_active_event(
        self,
        test_db_with_data: tuple[Path, Session],
        capsys: CaptureFixture,
    ) -> None:
        reload(data)
        # not event active
        with pytest.raises(RuntimeError):
            data.print_data_table(False, False)

        data.print_data_table(False, True)
        captured = capsys.readouterr()
        assert "AIMBAT data for all events" in captured.out

    def test_lib_print_data_table_with_active_event(
        self,
        test_db_with_active_event: tuple[Path, Session],
        capsys: CaptureFixture,
    ) -> None:
        reload(data)
        data.print_data_table(False, False)
        captured = capsys.readouterr()
        assert "AIMBAT data for event 2011-09-15 19:31:04.080000+00:00" in captured.out

        data.print_data_table(True, False)
        captured = capsys.readouterr()
        assert "AIMBAT data for event 2011-09-15 19:31:04" in captured.out

        data.print_data_table(False, True)
        captured = capsys.readouterr()
        assert "AIMBAT data for all events" in captured.out

        data.print_data_table(True, True)
        captured = capsys.readouterr()
        assert "AIMBAT data for all events" in captured.out

    def test_cli_data_list(
        self,
        test_db_with_active_event: tuple[Path, Session],
        capsys: CaptureFixture,
    ) -> None:
        reload(data)
        from aimbat.app import app

        app(["data", "list", "--no-format"])
        captured = capsys.readouterr()
        assert "AIMBAT data for event 2011-09-15 19:31:04.080000+00:00" in captured.out

        app(["data", "list"])
        captured = capsys.readouterr()
        assert "AIMBAT data for event 2011-09-15 19:31:04" in captured.out

        app(["data", "list", "--all"])
        captured = capsys.readouterr()
        assert "AIMBAT data for all events" in captured.out


class TestDataCompare(TestDataBase):
    def test_compare_aimbat_seis_to_sac_seis(
        self,
        sac_file_good: Path,
        sac_instance_good: SAC,
        test_db_with_project: tuple[Path, Session],
    ) -> None:
        reload(data)
        from aimbat.lib.models import AimbatSeismogram

        data.add_files_to_project(
            [sac_file_good],
            filetype=SeismogramFileType.SAC,
        )

        session = test_db_with_project[1]
        sac_seismogram = sac_instance_good.seismogram
        aimbat_seismogram = session.exec(select(AimbatSeismogram)).one()

        assert np.array_equal(aimbat_seismogram.data, sac_seismogram.data)
        assert aimbat_seismogram.delta == sac_seismogram.delta
        assert aimbat_seismogram.begin_time == sac_seismogram.begin_time
        assert len(aimbat_seismogram) == len(sac_seismogram)

    def test_compare_aimbat_station_to_sac_station(
        self,
        sac_file_good: Path,
        sac_instance_good: SAC,
        test_db_with_project: tuple[Path, Session],
    ) -> None:
        reload(data)
        from aimbat.lib.models import AimbatStation, AimbatSeismogram

        data.add_files_to_project([sac_file_good], filetype=SeismogramFileType.SAC)

        session = test_db_with_project[1]
        sac_station = sac_instance_good.station
        aimbat_seismogram = session.exec(select(AimbatSeismogram)).one()
        aimbat_station = session.exec(select(AimbatStation)).one()
        assert aimbat_seismogram.station == aimbat_station
        assert aimbat_station.name == sac_instance_good.kstnm
        assert aimbat_station.latitude == sac_station.latitude
        assert aimbat_station.longitude == sac_station.longitude
        assert aimbat_station.elevation == sac_station.elevation

    def test_compare_aimbat_event_to_sac_event(
        self,
        sac_file_good: Path,
        sac_instance_good: SAC,
        test_db_with_project: tuple[Path, Session],
    ) -> None:
        reload(data)
        from aimbat.lib.models import AimbatEvent, AimbatSeismogram

        data.add_files_to_project([sac_file_good], filetype=SeismogramFileType.SAC)

        session = test_db_with_project[1]
        sac_event = sac_instance_good.event
        aimbat_seismogram = session.exec(select(AimbatSeismogram)).one()
        aimbat_event = session.exec(select(AimbatEvent)).one()
        assert aimbat_seismogram.event == aimbat_event
        assert aimbat_event.latitude == sac_event.latitude
        assert aimbat_event.longitude == sac_event.longitude
        assert aimbat_event.depth == sac_event.depth
