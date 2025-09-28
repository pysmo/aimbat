from aimbat.config import Settings
from pysmo.classes import SAC
from datetime import datetime, timezone
from importlib import reload
from typing import Any
from sqlmodel import Session
from collections.abc import Generator
from pathlib import Path
import aimbat.lib.utils.checkdata as checkdata
import aimbat.lib.utils.sampledata as sampledata
import numpy as np
import os
import pytest


class TestUtilsBase:
    @pytest.fixture(autouse=True)
    def reload_modules(self, fixture_session_with_active_event: Session) -> None:
        reload(checkdata)
        reload(sampledata)

    @pytest.fixture
    def session(
        self, fixture_session_with_active_event: Session
    ) -> Generator[Session, Any, Any]:
        yield fixture_session_with_active_event

    @pytest.fixture(autouse=True)
    def download_dir(
        self,
        tmp_path_factory: pytest.TempPathFactory,
        patch_settings: Settings,
    ) -> Generator[Path, Any, Any]:
        tmp_dir = tmp_path_factory.mktemp("download_dir")
        patch_settings.sampledata_dir = tmp_dir
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

    def test_cli_usage(self, capsys: pytest.CaptureFixture) -> None:
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
    @pytest.mark.dependency(name="download_sampledata")
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

    def test_cli_usage(self, capsys: pytest.CaptureFixture) -> None:
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
