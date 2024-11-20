from pathlib import Path

from aimbat.lib.common import AimbatDataError
from pysmo import SAC
from click.testing import CliRunner
from datetime import datetime, timezone
import pytest
import numpy as np


class TestCheckData:
    def test_check_station_no_name(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_station

        assert sac_instance_good.station.name
        checkdata_station(sac_instance_good.station)
        sac_instance_good.kstnm = None
        with pytest.raises(AimbatDataError):
            checkdata_station(sac_instance_good.station)

    def test_check_station_no_latitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_station

        assert sac_instance_good.station.latitude
        checkdata_station(sac_instance_good.station)
        sac_instance_good.stla = None
        with pytest.raises(AimbatDataError):
            checkdata_station(sac_instance_good.station)

    def test_check_station_no_longitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_station

        assert sac_instance_good.station.longitude
        checkdata_station(sac_instance_good.station)
        sac_instance_good.stlo = None
        with pytest.raises(AimbatDataError):
            checkdata_station(sac_instance_good.station)

    def test_check_event_no_latitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_event

        assert sac_instance_good.event.latitude
        checkdata_event(sac_instance_good.event)
        sac_instance_good.evla = None
        with pytest.raises(AimbatDataError):
            checkdata_event(sac_instance_good.event)

    def test_check_event_no_longitude(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_event

        assert sac_instance_good.event.longitude
        checkdata_event(sac_instance_good.event)
        sac_instance_good.evlo = None
        with pytest.raises(AimbatDataError):
            checkdata_event(sac_instance_good.event)

    def test_check_event_no_time(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_event

        assert sac_instance_good.event.time
        checkdata_event(sac_instance_good.event)
        sac_instance_good.o = None
        with pytest.raises(AimbatDataError):
            checkdata_event(sac_instance_good.event)

    def test_check_seismogram_no_begin_time(self, sac_instance_good: SAC) -> None:
        from aimbat.lib.checkdata import checkdata_seismogram

        assert len(sac_instance_good.seismogram.data) > 0
        checkdata_seismogram(sac_instance_good.seismogram)
        sac_instance_good.seismogram.data = np.array([])
        with pytest.raises(AimbatDataError):
            checkdata_seismogram(sac_instance_good.seismogram)

    def test_cli_checkdata(self, project_directory: Path) -> None:
        """Test AIMBAT cli with checkdata subcommand."""
        from aimbat.lib import checkdata

        testfile = str(project_directory) + "/test.sac"

        sac = SAC()
        sac.write(testfile)

        runner = CliRunner()
        result = runner.invoke(checkdata.checkdata_cli)
        assert result.exit_code == 2
        assert "Error: Missing argument" in result.output

        result = runner.invoke(checkdata.checkdata_cli, [testfile])
        assert result.exit_code == 0
        for item in ["name", "latitude", "longitude"]:
            assert f"No station {item} found in file" in result.output
        for item in ["time", "latitude", "longitude"]:
            assert f"No event {item} found in file" in result.output
        assert "No seismogram data found in file" in result.output

        sac.station.name = "test"
        sac.station.latitude = 1.1
        sac.station.longitude = -23
        sac.event.time = datetime.now(timezone.utc)
        sac.event.latitude = 33
        sac.event.longitude = 19.1
        sac.seismogram.data = np.random.rand(100)
        sac.write(testfile)
        result = runner.invoke(checkdata.checkdata_cli, [testfile])
        assert result.exit_code == 0
        for item in ["name", "latitude", "longitude"]:
            assert f"No station {item} found in file" not in result.output
        for item in ["time", "latitude", "longitude"]:
            assert f"No event {item} found in file" not in result.output
        assert "No seismogram data found in file" not in result.output
