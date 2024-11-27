from aimbat.lib import data
from aimbat.app import app
from aimbat.lib.models import (
    AimbatEventParameters,
    AimbatFile,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
    AimbatEvent,
)
from aimbat.lib.types import SeismogramFileType
from sqlmodel import select
from typer.testing import CliRunner
from pysmo import SAC
import pytest
import numpy as np


class TestLibData:
    def test_sac_data(self, sac_file_good, sac_instance_good, db_session) -> None:  # type: ignore
        sac_seismogram = sac_instance_good.seismogram
        sac_station = sac_instance_good.station
        sac_event = sac_instance_good.event

        data.add_files_to_project(
            db_session, [sac_file_good], filetype=SeismogramFileType.SAC
        )

        select_file = select(AimbatFile).where(AimbatFile.filename == sac_file_good)
        select_seismogram = select(AimbatSeismogram).where(
            AimbatSeismogram.file_id == 1
        )

        aimbat_file = db_session.exec(select_file).one()
        assert sac_file_good == aimbat_file.filename
        assert 1 == aimbat_file.id

        aimbat_seismogram = db_session.exec(select_seismogram).one()
        assert aimbat_seismogram.station_id == 1
        assert aimbat_seismogram.event_id == 1
        assert aimbat_seismogram.begin_time == sac_seismogram.begin_time
        assert aimbat_seismogram.delta == sac_seismogram.delta
        assert len(aimbat_seismogram) == len(sac_seismogram)
        assert aimbat_seismogram.end_time == sac_seismogram.end_time
        assert isinstance(aimbat_seismogram.parameters, AimbatSeismogramParameters)

        new_data = np.random.rand(10)
        aimbat_seismogram.data = new_data
        assert len(aimbat_seismogram) == 10
        np.testing.assert_array_almost_equal(aimbat_seismogram.data, new_data)

        select_station = select(AimbatStation).where(
            AimbatStation.id == aimbat_seismogram.station_id
        )
        aimbat_station = db_session.exec(select_station).one()
        assert aimbat_station.name == sac_station.name
        assert aimbat_station.network == sac_station.network
        assert aimbat_station.latitude == sac_station.latitude
        assert aimbat_station.longitude == sac_station.longitude
        assert aimbat_station.elevation == sac_station.elevation

        select_event = select(AimbatEvent).where(
            AimbatEvent.id == aimbat_seismogram.station_id
        )
        aimbat_event = db_session.exec(select_event).one()
        assert aimbat_event.time == sac_event.time
        assert aimbat_event.latitude == sac_event.latitude
        assert aimbat_event.longitude == sac_event.longitude
        assert isinstance(aimbat_event.parameters, AimbatEventParameters)

        sac = SAC.from_file(sac_file_good)

        new_delta = sac.seismogram.delta * 2
        sac.seismogram.delta = new_delta
        assert sac.seismogram.delta == new_delta

        new_station_latitude = (np.random.random() - 0.5) * 90
        new_station_longitude = (np.random.random() - 0.5) * 180
        sac.station.latitude = new_station_latitude
        sac.station.longitude = new_station_longitude
        assert sac.station.latitude == new_station_latitude
        assert sac.station.longitude == new_station_longitude

        new_event_latitude = (np.random.random() - 0.5) * 90
        new_event_longitude = (np.random.random() - 0.5) * 180
        sac.event.latitude = new_event_latitude
        sac.event.longitude = new_event_longitude
        assert sac.event.latitude == new_event_latitude
        assert sac.event.longitude == new_event_longitude

        sac.write(sac_file_good)
        data.add_files_to_project(
            db_session, [sac_file_good], filetype=SeismogramFileType.SAC
        )
        aimbat_file = db_session.exec(select_file).one()
        assert sac_file_good == aimbat_file.filename
        assert 1 == aimbat_file.id
        select_seismogram = select(AimbatSeismogram).where(
            AimbatSeismogram.file_id == aimbat_file.id
        )
        aimbat_seismogram = db_session.exec(select_seismogram).one()
        assert aimbat_seismogram.delta == new_delta

        select_station = select(AimbatStation).where(
            AimbatStation.id == aimbat_seismogram.station_id
        )
        aimbat_station = db_session.exec(select_station).one()
        assert aimbat_station.latitude == pytest.approx(new_station_latitude)
        assert aimbat_station.longitude == pytest.approx(new_station_longitude)

        select_event = select(AimbatEvent).where(
            AimbatEvent.id == aimbat_seismogram.event_id
        )
        aimbat_event = db_session.exec(select_event).one()
        assert aimbat_event.latitude == pytest.approx(new_event_latitude)
        assert aimbat_event.longitude == pytest.approx(new_event_longitude)


class TestCliData:
    def test_sac_data(self, sac_file_good, db_url, monkeypatch) -> None:  # type: ignore
        """Test AIMBAT cli with data subcommand."""

        monkeypatch.setenv("COLUMNS", "1000")

        runner = CliRunner()

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["data"])
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "data", "add"])
        assert result.exit_code == 2

        result = runner.invoke(app, ["--db-url", db_url, "data", "add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "data", "list", "--all"])
        assert result.exit_code == 0
        assert sac_file_good in result.output

        result = runner.invoke(app, ["--db-url", db_url, "data", "list"])
        assert result.exit_code == 1

        result = runner.invoke(app, ["--db-url", db_url, "event", "activate", "1"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "data", "list"])
        assert result.exit_code == 0
        assert sac_file_good in result.output
