from pathlib import Path
from pysmo import SAC
from click.testing import CliRunner
from datetime import datetime, timezone
import numpy as np


class TestCliCheckData:
    def test_cli_checkdata(self, project_directory: Path) -> None:
        """Test AIMBAT cli with checkdata subcommand."""
        from aimbat.cli import checkdata

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
