from pathlib import Path

from aimbat.lib.checkdata import AimbatDataError
from pysmo import SAC
from click.testing import CliRunner
from datetime import datetime, timezone
import pytest
import numpy as np


class TestCheckData:

    def test_check_station_no_name(self, sac_good: SAC) -> None:
        from aimbat.lib.checkdata import check_station
        assert sac_good.station.name
        check_station(sac_good.station)
        sac_good.kstnm = None
        with pytest.raises(AimbatDataError):
            check_station(sac_good.station)

    def test_check_station_no_latitude(self, sac_good: SAC) -> None:
        from aimbat.lib.checkdata import check_station
        assert sac_good.station.latitude
        check_station(sac_good.station)
        sac_good.stla = None
        with pytest.raises(AimbatDataError):
            check_station(sac_good.station)

    def test_check_station_no_longitude(self, sac_good: SAC) -> None:
        from aimbat.lib.checkdata import check_station
        assert sac_good.station.longitude
        check_station(sac_good.station)
        sac_good.stlo = None
        with pytest.raises(AimbatDataError):
            check_station(sac_good.station)

    def test_check_event_no_latitude(self, sac_good: SAC) -> None:
        from aimbat.lib.checkdata import check_event
        assert sac_good.event.latitude
        check_event(sac_good.event)
        sac_good.evla = None
        with pytest.raises(AimbatDataError):
            check_event(sac_good.event)

    def test_check_event_no_longitude(self, sac_good: SAC) -> None:
        from aimbat.lib.checkdata import check_event
        assert sac_good.event.longitude
        check_event(sac_good.event)
        sac_good.evlo = None
        with pytest.raises(AimbatDataError):
            check_event(sac_good.event)

    def test_check_event_no_time(self, sac_good: SAC) -> None:
        from aimbat.lib.checkdata import check_event
        assert sac_good.event.time
        check_event(sac_good.event)
        sac_good.o = None
        with pytest.raises(AimbatDataError):
            check_event(sac_good.event)

    def test_check_seismogram_no_begin_time(self, sac_good: SAC) -> None:
        from aimbat.lib.checkdata import check_seismogram
        assert len(sac_good.seismogram.data) > 0
        check_seismogram(sac_good.seismogram)
        sac_good.seismogram.data = np.array([])
        with pytest.raises(AimbatDataError):
            check_seismogram(sac_good.seismogram)


@pytest.mark.depends(depends=["TestCheckData"])
@pytest.mark.usefixtures("tmp_project")
def test_cli_checkdata(project_directory: Path) -> None:
    """Test AIMBAT cli with checkdata subcommand."""
    from aimbat.lib import checkdata

    testfile = str(project_directory) + '/test.sac'

    sac = SAC()
    sac.write(testfile)

    runner = CliRunner()
    result = runner.invoke(checkdata.cli)
    assert result.exit_code == 2
    assert 'Error: Missing argument' in result.output

    result = runner.invoke(checkdata.cli, [testfile])
    assert result.exit_code == 0
    for item in ['name', 'latitude', 'longitude']:
        assert f'No station {item} found in file' in result.output
    for item in ['time', 'latitude', 'longitude']:
        assert f'No event {item} found in file' in result.output
    assert 'No seismogram data found in file' in result.output

    sac.station.name = "test"
    sac.station.latitude = 1.1
    sac.station.longitude = -23
    sac.event.time = datetime.now(timezone.utc)
    sac.event.latitude = 33
    sac.event.longitude = 19.1
    sac.seismogram.data = np.random.rand(100)
    sac.write(testfile)
    result = runner.invoke(checkdata.cli, [testfile])
    assert result.exit_code == 0
    for item in ['name', 'latitude', 'longitude']:
        assert f'No station {item} found in file' not in result.output
    for item in ['time', 'latitude', 'longitude']:
        assert f'No event {item} found in file' not in result.output
    assert 'No seismogram data found in file' not in result.output
