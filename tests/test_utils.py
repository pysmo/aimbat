from typer.testing import CliRunner
from pysmo import SAC
from datetime import datetime, timezone
import numpy as np
import os


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

    def test_plotseis(self, test_data, db_session, mock_show) -> None:  # type: ignore
        from aimbat.lib import data, utils

        data.add_files_to_project(db_session, test_data, filetype="sac")
        utils.plotseis(db_session, 1)


class TestCliUtils:
    def test_sampledata(self, tmp_path_factory, db_url, monkeypatch) -> None:  # type: ignore
        """Test AIMBAT cli with utils sampledata subcommand."""

        monkeypatch.setenv("COLUMNS", "1000")

        from aimbat.app import app

        sampledata_dir = tmp_path_factory.mktemp("sampledata")

        runner = CliRunner()
        result = runner.invoke(app, "utils", "sampledata")
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 0

        result = runner.invoke(
            app,
            [
                "--db-url",
                db_url,
                "defaults",
                "set",
                "sampledata_dir",
                str(sampledata_dir),
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            app,
            [
                "--db-url",
                db_url,
                "defaults",
                "list",
            ],
        )
        assert str(sampledata_dir) in result.output

        assert len(os.listdir((sampledata_dir))) == 0
        result = runner.invoke(
            app, ["--db-url", db_url, "utils", "sampledata", "download"]
        )
        assert result.exit_code == 0
        assert len(os.listdir((sampledata_dir))) > 0
        #
        # can't download if it is already there
        result = runner.invoke(
            app, ["--db-url", db_url, "utils", "sampledata", "download"]
        )
        assert result.exit_code == 1

        # unless we use force
        result = runner.invoke(
            app, ["--db-url", db_url, "utils", "sampledata", "download", "--force"]
        )
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["--db-url", db_url, "utils", "sampledata", "delete"]
        )
        assert result.exit_code == 0
        assert not sampledata_dir.exists()

    def test_checkdata(self, tmp_path_factory) -> None:  # type: ignore
        """Test AIMBAT cli with checkdata subcommand."""
        from aimbat.app import app

        testfile = str(tmp_path_factory.mktemp("checkdata")) + "/test.sac"

        sac = SAC()
        sac.write(testfile)

        runner = CliRunner()
        result = runner.invoke(app, ["utils", "checkdata"])
        assert result.exit_code == 2

        result = runner.invoke(app, ["utils", "checkdata", testfile])
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
        result = runner.invoke(app, ["utils", "checkdata", testfile])
        assert result.exit_code == 0
        for item in ["name", "latitude", "longitude"]:
            assert f"No station {item} found in file" not in result.output
        for item in ["time", "latitude", "longitude"]:
            assert f"No event {item} found in file" not in result.output
        assert "No seismogram data found in file" not in result.output

    def test_plotseis(self, test_data_string, db_url, mock_show) -> None:  # type: ignore
        """Test AIMBAT cli with utils subcommand."""

        from aimbat.app import app

        runner = CliRunner()

        result = runner.invoke(app, ["utils"])
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 0

        args = ["--db-url", db_url, "data", "add"]
        args.extend(test_data_string)
        result = runner.invoke(app, args)
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "utils", "plotseis", "1"])
        assert result.exit_code == 0

        # result = runner.invoke(
        #     app, ["--db-url", db_url, "--use-qt", "utils", "plotseis", "1"]
        # )
        # assert result.exit_code == 0
