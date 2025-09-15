from pysmo.classes import SAC
from datetime import datetime, timezone
import numpy as np
import os
import pytest
from pathlib import Path


class TestLibUtils:
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


class TestCliUtils:
    def test_sampledata(
        self,
        tmp_path_factory: pytest.TempPathFactory,
        db_url: str,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Test AIMBAT cli with utils sampledata subcommand."""

        monkeypatch.setenv("COLUMNS", "1000")

        from aimbat.app import app

        sampledata_dir = Path(tmp_path_factory.mktemp("sampledata"))

        app(["utils", "sampledata"])
        assert "Usage" in capsys.readouterr().out

        app(["project", "create", "--db-url", db_url])

        app(
            [
                "defaults",
                "set",
                "sampledata_dir",
                str(sampledata_dir),
                "--db-url",
                db_url,
            ]
        )

        app(["defaults", "list", "--db-url", db_url])
        assert str(sampledata_dir) in capsys.readouterr().out

        assert len(os.listdir((sampledata_dir))) == 0
        app(["utils", "sampledata", "download", "--db-url", db_url])
        assert len(os.listdir((sampledata_dir))) > 0

        # can't download if it is already there
        with pytest.raises(RuntimeError):
            app(["utils", "sampledata", "download", "--db-url", db_url])

        # unless we use force
        app(["utils", "sampledata", "download", "--force", "--db-url", db_url])

        app(["utils", "sampledata", "delete", "--db-url", db_url])
        assert not sampledata_dir.exists()

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
