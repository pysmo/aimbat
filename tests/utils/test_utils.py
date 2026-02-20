from aimbat._config import Settings
from aimbat.app import app
from pysmo.classes import SAC
from datetime import datetime, timezone
from typing import Any
from sqlmodel import Session
from sqlalchemy import Engine
from collections.abc import Generator
from pathlib import Path
import aimbat.utils._checkdata as _checkdata
import aimbat.utils._sampledata as _sampledata
import numpy as np
import os
import pytest


class TestUtilsBase:
    @pytest.fixture
    def session(
        self, fixture_engine_session_with_active_event: tuple[Engine, Session]
    ) -> Generator[Session, Any, Any]:
        _, session = fixture_engine_session_with_active_event
        yield session

    @pytest.fixture(autouse=True)
    def download_dir(
        self,
        session: Session,
        tmp_path_factory: pytest.TempPathFactory,
        patch_settings: Settings,
    ) -> Generator[Path, Any, Any]:
        tmp_dir = tmp_path_factory.mktemp("download_dir")
        patch_settings.sampledata_dir = tmp_dir
        yield tmp_dir


class TestUtilsCheckData(TestUtilsBase):
    def test_check_station_no_name(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.station.name
        _checkdata.checkdata_station(sac_instance_good.station)
        sac_instance_good.kstnm = None
        issues = _checkdata.checkdata_station(sac_instance_good.station)
        assert "No station name" in issues[0]

    def test_check_station_no_latitude(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.station.latitude
        _checkdata.checkdata_station(sac_instance_good.station)
        sac_instance_good.stla = None
        issues = _checkdata.checkdata_station(sac_instance_good.station)
        assert "No station latitude" in issues[0]

    def test_check_station_no_longitude(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.station.longitude
        _checkdata.checkdata_station(sac_instance_good.station)
        sac_instance_good.stlo = None
        issues = _checkdata.checkdata_station(sac_instance_good.station)
        assert "No station longitude" in issues[0]

    def test_check_event_no_latitude(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.event.latitude
        _checkdata.checkdata_event(sac_instance_good.event)
        sac_instance_good.evla = None
        issues = _checkdata.checkdata_event(sac_instance_good.event)
        assert "No event latitude" in issues[0]

    def test_check_event_no_longitude(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.event.longitude
        _checkdata.checkdata_event(sac_instance_good.event)
        sac_instance_good.evlo = None
        issues = _checkdata.checkdata_event(sac_instance_good.event)
        assert "No event longitude" in issues[0]

    def test_check_event_no_time(self, sac_instance_good: SAC) -> None:
        assert sac_instance_good.event.time
        _checkdata.checkdata_event(sac_instance_good.event)
        sac_instance_good.o = None
        issues = _checkdata.checkdata_event(sac_instance_good.event)
        assert "No event time" in issues[0]

    def test_check_seismogram_no_begin_time(self, sac_instance_good: SAC) -> None:
        assert len(sac_instance_good.seismogram.data) > 0
        _checkdata.checkdata_seismogram(sac_instance_good.seismogram)
        sac_instance_good.seismogram.data = np.array([])
        issues = _checkdata.checkdata_seismogram(sac_instance_good.seismogram)
        assert "No seismogram data" in issues[0]

    def test_cli_usage(self, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(["utils", "checkdata", "--help"])

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        assert "Usage" in captured.out

    def test_cli_checkdata(
        self, tmp_path_factory: pytest.TempPathFactory, capsys: pytest.CaptureFixture
    ) -> None:
        """Test AIMBAT cli with checkdata subcommand."""

        testfile = str(tmp_path_factory.mktemp("checkdata")) + "/test.sac"

        sac = SAC()
        sac.write(testfile)

        with pytest.raises(SystemExit) as excinfo:
            app(["utils", "checkdata", testfile])
        assert excinfo.value.code == 0
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
        with pytest.raises(SystemExit) as excinfo:
            app(["utils", "checkdata", testfile])
        assert excinfo.value.code == 0
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
        _sampledata.download_sampledata()
        assert len(os.listdir(download_dir)) > 0
        with pytest.raises(FileExistsError):
            _sampledata.download_sampledata()
        _sampledata.download_sampledata(force=True)

    @pytest.mark.dependency(depends=["download_sampledata"])
    def test_lib_delete_sampledata(self, download_dir: Path) -> None:
        _sampledata.download_sampledata()
        assert len(os.listdir(download_dir)) > 0
        _sampledata.delete_sampledata()
        assert download_dir.exists() is False

    def test_cli_usage(self, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(["utils", "sampledata", "--help"])
        assert excinfo.value.code == 0
        assert "Usage" in capsys.readouterr().out

    def test_cli_download_sampledata(self, download_dir: Path) -> None:
        assert len(os.listdir((download_dir))) == 0
        with pytest.raises(SystemExit) as excinfo:
            app(["utils", "sampledata", "download"])
        assert excinfo.value.code == 0
        assert len(os.listdir((download_dir))) > 0

        # can't download if it is already there
        with pytest.raises(FileExistsError):
            app(["utils", "sampledata", "download"])

        # unless we use force
        with pytest.raises(SystemExit) as excinfo:
            app(["utils", "sampledata", "download", "--force"])
        assert excinfo.value.code == 0

    def test_cli__delete_sampledata(self, download_dir: Path) -> None:
        assert len(os.listdir((download_dir))) == 0
        with pytest.raises(SystemExit) as excinfo:
            app(["utils", "sampledata", "download"])
        assert excinfo.value.code == 0
        assert len(os.listdir((download_dir))) > 0

        with pytest.raises(SystemExit) as excinfo:
            app(["utils", "sampledata", "delete"])
        assert excinfo.value.code == 0
        assert not download_dir.exists()
