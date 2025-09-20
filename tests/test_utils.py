from __future__ import annotations
from pysmo.classes import SAC
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import numpy as np
import os
import platform
import pytest
from pathlib import Path

if TYPE_CHECKING:
    from pytest import CaptureFixture, TempPathFactory
    from sqlmodel import Session
    from sqlalchemy.engine import Engine
    from collections.abc import Generator
    from typing import Any


class TestLibUtilsBase:
    @pytest.fixture
    def session(
        self, test_db_with_project: tuple[Path, str, Engine, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_project[3]

    @pytest.fixture
    def download_dir(
        self, tmp_path_factory: TempPathFactory
    ) -> Generator[Path, Any, Any]:
        yield Path(tmp_path_factory.mktemp("download"))


class TestLibUtilsCheckData(TestLibUtilsBase):
    def test_check_station_no_name(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.utils.checkdata import checkdata_station

        assert sac_instance_good.station.name
        checkdata_station(sac_instance_good.station)
        sac_instance_good.kstnm = None
        issues = checkdata_station(sac_instance_good.station)
        assert "No station name" in issues[0]

    def test_check_station_no_latitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.utils.checkdata import checkdata_station

        assert sac_instance_good.station.latitude
        checkdata_station(sac_instance_good.station)
        sac_instance_good.stla = None
        issues = checkdata_station(sac_instance_good.station)
        assert "No station latitude" in issues[0]

    def test_check_station_no_longitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.utils.checkdata import checkdata_station

        assert sac_instance_good.station.longitude
        checkdata_station(sac_instance_good.station)
        sac_instance_good.stlo = None
        issues = checkdata_station(sac_instance_good.station)
        assert "No station longitude" in issues[0]

    def test_check_event_no_latitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.utils.checkdata import checkdata_event

        assert sac_instance_good.event.latitude
        checkdata_event(sac_instance_good.event)
        sac_instance_good.evla = None
        issues = checkdata_event(sac_instance_good.event)
        assert "No event latitude" in issues[0]

    def test_check_event_no_longitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.utils.checkdata import checkdata_event

        assert sac_instance_good.event.longitude
        checkdata_event(sac_instance_good.event)
        sac_instance_good.evlo = None
        issues = checkdata_event(sac_instance_good.event)
        assert "No event longitude" in issues[0]

    def test_check_event_no_time(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.utils.checkdata import checkdata_event

        assert sac_instance_good.event.time
        checkdata_event(sac_instance_good.event)
        sac_instance_good.o = None
        issues = checkdata_event(sac_instance_good.event)
        assert "No event time" in issues[0]

    def test_check_seismogram_no_begin_time(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.utils.checkdata import checkdata_seismogram

        assert len(sac_instance_good.seismogram.data) > 0
        checkdata_seismogram(sac_instance_good.seismogram)
        sac_instance_good.seismogram.data = np.array([])
        issues = checkdata_seismogram(sac_instance_good.seismogram)
        assert "No seismogram data" in issues[0]


@pytest.mark.dependency(depends=["create_project"], scope="session")
class TestLibUtilsSampleData(TestLibUtilsBase):
    @pytest.mark.dependency(
        name="download_sampledata", depends=["set_default"], scope="session"
    )
    def test_download_sampledata(self, session: Session, download_dir: Path) -> None:
        from aimbat.lib.utils.sampledata import download_sampledata
        from aimbat.lib.defaults import set_default, ProjectDefault

        set_default(session, ProjectDefault.SAMPLEDATA_DIR, str(download_dir))
        assert len(os.listdir(download_dir)) == 0
        download_sampledata(session)
        assert len(os.listdir(download_dir)) > 0
        with pytest.raises(FileExistsError):
            download_sampledata(session)
        download_sampledata(session, force=True)

    @pytest.mark.dependency(depends=["download_sampledata"])
    def test_delete_sampledata(self, session: Session, download_dir: Path) -> None:
        from aimbat.lib.utils.sampledata import delete_sampledata, download_sampledata
        from aimbat.lib.defaults import set_default, ProjectDefault

        set_default(session, ProjectDefault.SAMPLEDATA_DIR, str(download_dir))
        download_sampledata(session)
        assert len(os.listdir(download_dir)) > 0
        delete_sampledata(session)
        assert download_dir.exists() is False


class TestCliUtilsBase:
    @pytest.fixture
    def db_url(self, test_db_with_project: tuple[Path, str, Engine, Session]) -> str:
        url = test_db_with_project[1]
        return url

    @pytest.fixture
    def session(
        self, test_db_with_project: tuple[Path, str, Engine, Session]
    ) -> Session:
        return test_db_with_project[3]

    @pytest.fixture
    def download_dir(self, tmp_path_factory: TempPathFactory) -> Path:
        return Path(tmp_path_factory.mktemp("download"))


class TestCliUtilsSampleData(TestCliUtilsBase):
    def test_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["utils", "sampledata"])
        assert "Usage" in capsys.readouterr().out

    @pytest.mark.skipif(
        platform.system() == "Darwin", reason="Doesn't run on github actions"
    )
    def test_download_sampledata(
        self,
        db_url: str,
        session: Session,
        download_dir: Path,
    ) -> None:
        from aimbat.app import app
        from aimbat.lib.defaults import set_default, ProjectDefault

        set_default(session, ProjectDefault.SAMPLEDATA_DIR, str(download_dir))

        assert len(os.listdir((download_dir))) == 0
        app(["utils", "sampledata", "download", "--db-url", db_url])
        assert len(os.listdir((download_dir))) > 0

        # can't download if it is already there
        with pytest.raises(FileExistsError):
            app(["utils", "sampledata", "download", "--db-url", db_url])

        # unless we use force
        app(["utils", "sampledata", "download", "--force", "--db-url", db_url])

    def test_delete_sampledata(
        self,
        db_url: str,
        session: Session,
        download_dir: Path,
    ) -> None:
        from aimbat.app import app
        from aimbat.lib.defaults import set_default, ProjectDefault

        set_default(session, ProjectDefault.SAMPLEDATA_DIR, str(download_dir))

        assert len(os.listdir((download_dir))) == 0
        app(["utils", "sampledata", "download", "--db-url", db_url])
        assert len(os.listdir((download_dir))) > 0

        app(["utils", "sampledata", "delete", "--db-url", db_url])
        assert not download_dir.exists()


class TestCliUtilsCheckData(TestCliUtilsBase):
    def test_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["utils", "checkdata", "--help"])
        assert "Usage" in capsys.readouterr().out

    def test_checkdata(
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
