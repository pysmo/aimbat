from __future__ import annotations
from pysmo.classes import SAC
from datetime import datetime, timezone
from importlib import reload
from typing import TYPE_CHECKING
import aimbat.lib.utils.checkdata as checkdata
import aimbat.lib.utils.sampledata as sampledata
import numpy as np
import os
import pytest
from pathlib import Path

if TYPE_CHECKING:
    from pytest import CaptureFixture, TempPathFactory, MonkeyPatch
    from sqlmodel import Session
    from collections.abc import Generator
    from typing import Any


class TestUtilsBase:
    @pytest.fixture(autouse=True)
    def reload_modules(self, test_db_with_active_event: tuple[Path, Session]) -> None:
        reload(checkdata)
        reload(sampledata)

    @pytest.fixture
    def session(
        self, test_db_with_active_event: tuple[Path, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_active_event[1]

    @pytest.fixture(autouse=True)
    def download_dir(
        self, tmp_path_factory: TempPathFactory, monkeypatch: MonkeyPatch
    ) -> Generator[Path, Any, Any]:
        tmp_dir = tmp_path_factory.mktemp("download_dir")
        monkeypatch.setenv("AIMBAT_SAMPLEDATA_DIR", str(tmp_dir))
        yield tmp_dir


class TestUtilsCheckData(TestUtilsBase):
    def test_check_station_no_name(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.station.name
        checkdata.checkdata_station(sac_instance_good.station)
        sac_instance_good.kstnm = None
        issues = checkdata.checkdata_station(sac_instance_good.station)
        assert "No station name" in issues[0]

    def test_check_station_no_latitude(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.station.latitude
        checkdata.checkdata_station(sac_instance_good.station)
        sac_instance_good.stla = None
        issues = checkdata.checkdata_station(sac_instance_good.station)
        assert "No station latitude" in issues[0]

    def test_check_station_no_longitude(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.station.longitude
        checkdata.checkdata_station(sac_instance_good.station)
        sac_instance_good.stlo = None
        issues = checkdata.checkdata_station(sac_instance_good.station)
        assert "No station longitude" in issues[0]

    def test_check_event_no_latitude(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.event.latitude
        checkdata.checkdata_event(sac_instance_good.event)
        sac_instance_good.evla = None
        issues = checkdata.checkdata_event(sac_instance_good.event)
        assert "No event latitude" in issues[0]

    def test_check_event_no_longitude(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.event.longitude
        checkdata.checkdata_event(sac_instance_good.event)
        sac_instance_good.evlo = None
        issues = checkdata.checkdata_event(sac_instance_good.event)
        assert "No event longitude" in issues[0]

    def test_check_event_no_time(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.event.time
        checkdata.checkdata_event(sac_instance_good.event)
        sac_instance_good.o = None
        issues = checkdata.checkdata_event(sac_instance_good.event)
        assert "No event time" in issues[0]

    def test_check_seismogram_no_begin_time(self, sac_instance_good: SAC) -> None:
        assert len(sac_instance_good.seismogram.data) > 0
        checkdata.checkdata_seismogram(sac_instance_good.seismogram)
        sac_instance_good.seismogram.data = np.array([])
        issues = checkdata.checkdata_seismogram(sac_instance_good.seismogram)
        assert "No seismogram data" in issues[0]

    def test_cli_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["utils", "checkdata", "--help"])
        assert "Usage" in capsys.readouterr().out

    def test_cli_checkdata(
        self, tmp_path_factory: pytest.TempPathFactory, capsys: pytest.CaptureFixture
    ) -> None:
        """Test AIMBAT cli with checkdata subcommand."""
        from aimbat.app import app

        testfile = str(tmp_path_factory.mktemp("checkdata")) + "/test.sac"

        sac = SAC()
        sac.write(testfile)

        app(["utils", "checkdata", testfile])
        output = capsys.readouterr().out
        for item in ["name", "latitude", "longitude"]:
            assert f"No station {item} found in file" in output
        for item in ["time", "latitude", "longitude"]:
            assert f"No event {item} found in file" in output
        assert "No seismogram data found in file" in output

        sac.station.name = "test"
        sac.station.latitude = 1.1
        sac.station.longitude = -23
        sac.event.time = datetime.now(timezone.utc)
        sac.event.latitude = 33
        sac.event.longitude = 19.1
        sac.seismogram.data = np.random.rand(100)
        sac.write(testfile)
        app(["utils", "checkdata", testfile])
        output = capsys.readouterr().out
        for item in ["name", "latitude", "longitude"]:
            assert f"No station {item} found in file" not in output
        for item in ["time", "latitude", "longitude"]:
            assert f"No event {item} found in file" not in output
        assert "No seismogram data found in file" not in output


class TestUtilsSampleData(TestUtilsBase):
    def test_lib_download_sampledata(self, download_dir: Path) -> None:
        assert len(os.listdir(download_dir)) == 0
        sampledata.download_sampledata()
        assert len(os.listdir(download_dir)) > 0
        with pytest.raises(FileExistsError):
            sampledata.download_sampledata()
        sampledata.download_sampledata(force=True)

    @pytest.mark.dependency(depends=["download_sampledata"])
    def test_lib_delete_sampledata(self, download_dir: Path) -> None:
        sampledata.download_sampledata()
        assert len(os.listdir(download_dir)) > 0
        sampledata.delete_sampledata()
        assert download_dir.exists() is False

    def test_cli_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["utils", "sampledata"])
        assert "Usage" in capsys.readouterr().out

    def test_cli_download_sampledata(self, download_dir: Path) -> None:
        from aimbat.app import app

        assert len(os.listdir((download_dir))) == 0
        app(["utils", "sampledata", "download"])
        assert len(os.listdir((download_dir))) > 0

        # can't download if it is already there
        with pytest.raises(FileExistsError):
            app(["utils", "sampledata", "download"])

        # unless we use force
        app(["utils", "sampledata", "download", "--force"])

    def test_cli__delete_sampledata(self, download_dir: Path) -> None:
        from aimbat.app import app

        assert len(os.listdir((download_dir))) == 0
        app(["utils", "sampledata", "download"])
        assert len(os.listdir((download_dir))) > 0

        app(["utils", "sampledata", "delete"])
        assert not download_dir.exists()


class TestUtilsDefaultsTable(TestUtilsBase):
    def test_lib_print_defaullts(self, capsys: CaptureFixture) -> None:
        import aimbat.lib.defaults as defaults

        defaults.print_defaults_table()

        output = capsys.readouterr().out
        assert "AIMBAT defaults" in output
        assert "AIMBAT project file location." in output

    def test_cli_print_defaullts(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["utils", "defaults"])

        output = capsys.readouterr().out
        assert "AIMBAT defaults" in output
        assert "AIMBAT project file location." in output
