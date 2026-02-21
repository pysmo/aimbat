from aimbat.app import app
from aimbat.aimbat_types import DataType
from aimbat.models import AimbatDataSource
from pysmo.classes import SAC
from sqlalchemy.exc import NoResultFound
from sqlmodel import select, Session
from sqlalchemy import Engine
from pathlib import Path
from pydantic import TypeAdapter
import aimbat.core._data as data
import pytest
import numpy as np
import json


class TestDataBase:
    """Base class for testing the data module."""


class TestDataAdd(TestDataBase):
    def test_lib_add_sac_file_to_project(
        self,
        sac_file_good: Path,
        fixture_engine_session_with_project: tuple[Engine, Session],
    ) -> None:
        engine, session = fixture_engine_session_with_project

        # do this 2 times to verify nothing changes
        for _ in range(2):
            data.add_files_to_project(
                session,
                [sac_file_good],
                datatype=DataType.SAC,
            )

            seismogram_filename = session.exec(
                select(AimbatDataSource.sourcename)
            ).one()
            assert seismogram_filename == str(sac_file_good)

    def test_cli_data_add(
        self,
        sac_file_good: Path,
        fixture_engine_session_with_project: tuple[Engine, Session],
    ) -> None:
        sac_file_good_as_string = str(sac_file_good)
        engine, session = fixture_engine_session_with_project

        with pytest.raises(SystemExit) as excinfo:
            app(["data", "add", "--no-progress", sac_file_good_as_string])

        assert excinfo.value.code == 0
        session.flush()

        seismogram_filename = session.exec(select(AimbatDataSource.sourcename)).one()
        assert seismogram_filename == str(sac_file_good)


class TestDataTable(TestDataBase):
    def test_lib_print_data_table_without_active_event(
        self,
        fixture_session_with_data: Session,
        capsys: pytest.CaptureFixture,
    ) -> None:

        session = fixture_session_with_data
        # no event active
        with pytest.raises(NoResultFound):
            data.print_data_table(session, False)

        data.print_data_table(session, False, True)
        captured = capsys.readouterr()
        assert "AIMBAT data for all events" in captured.out

    @pytest.mark.parametrize(
        "short, all_events, expected",
        [
            (True, True, "AIMBAT data for all events"),
            (True, False, "AIMBAT data for event 2011-09-15 19:31:04"),
            (False, True, "AIMBAT data for all events"),
            (True, False, "AIMBAT data for event 2011-09-15 19:31:04"),
        ],
    )
    def test_lib_print_data_table_with_active_event(
        self,
        fixture_engine_session_with_active_event: tuple[Engine, Session],
        capsys: pytest.CaptureFixture,
        short: bool,
        all_events: bool,
        expected: str,
    ) -> None:
        _, session = fixture_engine_session_with_active_event
        data.print_data_table(session, short, all_events)
        captured = capsys.readouterr()
        assert expected in captured.out

    @pytest.mark.parametrize(
        "cli_args,expected",
        [
            (["--all", "--no-short"], "AIMBAT data for all events"),
            (["--no-short"], "AIMBAT data for event 2011-09-15 19:31:04.080000+00:00"),
            (["--all"], "AIMBAT data for all events"),
            ([], "AIMBAT data for event 2011-09-15 19:31:04"),
        ],
    )
    def test_cli_data_list(
        self,
        fixture_engine_session_with_active_event: tuple[Engine, Session],
        capsys: pytest.CaptureFixture,
        cli_args: list[str],
        expected: str,
    ) -> None:
        cmd = ["data", "list"]
        cmd.extend(cli_args)
        with pytest.raises(SystemExit) as excinfo:
            app(cmd)

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        assert expected in captured.out


class TestDataDump(TestDataBase):
    def test_lib_dump_data(
        self,
        fixture_session_with_data: Session,
    ) -> None:
        json_data = data.dump_data_table_to_json(fixture_session_with_data)
        adapter = TypeAdapter(list[AimbatDataSource])
        adapter.validate_json(json_data)

    def test_cli_dump_data(
        self,
        fixture_session_with_data: Session,
        capsys: pytest.CaptureFixture,
    ) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(["data", "dump"])

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatDataSource(**i)


class TestDataCompare(TestDataBase):
    def test_compare_aimbat_seis_to_sac_seis(
        self,
        sac_file_good: Path,
        sac_instance_good: SAC,
        fixture_engine_session_with_project: tuple[Engine, Session],
    ) -> None:
        from aimbat.models import AimbatSeismogram

        _, session = fixture_engine_session_with_project

        data.add_files_to_project(
            session,
            [sac_file_good],
            datatype=DataType.SAC,
        )

        sac_seismogram = sac_instance_good.seismogram
        aimbat_seismogram = session.exec(select(AimbatSeismogram)).one()

        assert np.array_equal(aimbat_seismogram.data, sac_seismogram.data)
        assert aimbat_seismogram.delta == sac_seismogram.delta
        assert (
            pytest.approx(aimbat_seismogram.begin_time.timestamp())
            == sac_seismogram.begin_time.timestamp()
        )
        assert len(aimbat_seismogram) == len(sac_seismogram)

    def test_compare_aimbat_station_to_sac_station(
        self,
        sac_file_good: Path,
        sac_instance_good: SAC,
        fixture_engine_session_with_project: tuple[Engine, Session],
    ) -> None:
        from aimbat.models import AimbatStation, AimbatSeismogram

        _, session = fixture_engine_session_with_project

        data.add_files_to_project(session, [sac_file_good], datatype=DataType.SAC)

        sac_station = sac_instance_good.station
        aimbat_seismogram = session.exec(select(AimbatSeismogram)).one()
        aimbat_station = session.exec(select(AimbatStation)).one()
        assert aimbat_seismogram.station == aimbat_station
        assert aimbat_station.name == sac_instance_good.kstnm
        assert aimbat_station.latitude == sac_station.latitude
        assert aimbat_station.longitude == sac_station.longitude
        assert aimbat_station.elevation == sac_station.elevation

    def test_compare_aimbat_event_to_sac_event(
        self,
        sac_file_good: Path,
        sac_instance_good: SAC,
        fixture_engine_session_with_project: tuple[Engine, Session],
    ) -> None:
        from aimbat.models import AimbatEvent, AimbatSeismogram

        _, session = fixture_engine_session_with_project

        data.add_files_to_project(session, [sac_file_good], datatype=DataType.SAC)

        sac_event = sac_instance_good.event
        aimbat_seismogram = session.exec(select(AimbatSeismogram)).one()
        aimbat_event = session.exec(select(AimbatEvent)).one()
        assert aimbat_seismogram.event == aimbat_event
        assert aimbat_event.latitude == sac_event.latitude
        assert aimbat_event.longitude == sac_event.longitude
        assert aimbat_event.depth == sac_event.depth
