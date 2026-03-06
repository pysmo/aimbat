"""Integration tests for adding data to the project (aimbat.core._data)."""

import json
import uuid
import pytest
from pathlib import Path
from pandas import Timestamp
from sqlalchemy import Engine
from sqlmodel import Session, select
from pydantic import ValidationError
from pysmo.classes import SAC
from aimbat.io import DataType
from aimbat.core import (
    add_data_to_project,
    get_data_for_event,
    dump_data_table_to_json,
    get_default_event,
)
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatSeismogram,
    AimbatStation,
)
from collections.abc import Generator

# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------


_STATION_DATA: dict = {
    "name": "ANMO",
    "network": "IU",
    "location": "00",
    "channel": "BHZ",
    "latitude": 34.9459,
    "longitude": -106.4572,
    "elevation": 1820.0,
}

_EVENT_DATA: dict = {
    "time": "2020-01-01T00:00:00Z",
    "latitude": 35.0,
    "longitude": -120.0,
    "depth": 10.0,
}


@pytest.fixture()
def station_json(tmp_path: Path) -> Path:
    """Path to a temporary JSON file containing a station record.

    Args:
        tmp_path: The pytest tmp_path fixture.

    Returns:
        Path to the JSON station file.
    """
    path = tmp_path / "station.json"
    path.write_text(json.dumps(_STATION_DATA))
    return path


@pytest.fixture()
def event_json(tmp_path: Path) -> Path:
    """Path to a temporary JSON file containing an event record.

    Args:
        tmp_path: The pytest tmp_path fixture.

    Returns:
        Path to the JSON event file.
    """
    path = tmp_path / "event.json"
    path.write_text(json.dumps(_EVENT_DATA))
    return path


# ===================================================================
# Session-level tests (patched_session / loaded_session)
# ===================================================================


class TestAddDataToProject:
    @pytest.fixture
    def session(self, patched_session: Session) -> Generator[Session, None, None]:
        """Provides a database session for tests.

        Args:
            patched_session (Session): A patched SQLAlchemy session fixture.
        """
        yield patched_session

    def test_add_single_sac_file(self, sac_file_good: Path, session: Session) -> None:
        """Verifies adding a single valid SAC file to the project.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        datasource = session.exec(select(AimbatDataSource.sourcename)).all()
        assert len(datasource) == 0, "Expected no data sources before adding files."

        # do this 2 times to verify we can only add the same file once and that nothing changes on the second attempt
        for _ in range(2):
            add_data_to_project(
                session,
                [sac_file_good],
                data_type=DataType.SAC,
            )
            seismogram_filename = session.exec(
                select(AimbatDataSource.sourcename)
            ).one()
            assert seismogram_filename == str(sac_file_good)

    def test_add_multiple_sac_files(
        self, multi_event_data: list[Path], session: Session
    ) -> None:
        """Verifies adding multiple SAC files to the project at once.

        Args:
            multi_event_data (list[Path]): List of paths to SAC files.
            session (Session): Database session.
        """
        datasource = session.exec(select(AimbatDataSource.sourcename)).all()
        assert len(datasource) == 0, "Expected no data sources before adding files."

        add_data_to_project(
            session,
            multi_event_data,
            data_type=DataType.SAC,
        )

        seismogram_filenames = session.exec(select(AimbatDataSource.sourcename)).all()
        assert sorted(seismogram_filenames) == sorted(
            [str(path) for path in multi_event_data]
        ), "Expected all files from multi_event to be added as data sources."

    def test_add_nonexistent_file(self, session: Session) -> None:
        """Verifies that adding a non-existent file raises FileNotFoundError.

        Args:
            session (Session): Database session.
        """
        non_existent_file = Path("this_file_does_not_exist.sac")
        with pytest.raises(FileNotFoundError):
            add_data_to_project(
                session,
                [non_existent_file],
                data_type=DataType.SAC,
            )

    def test_add_mixed_valid_and_invalid_files(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """Verifies that adding a mix of valid and invalid files raises an error and adds nothing.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        non_existent_file = Path("this_file_does_not_exist.sac")
        with pytest.raises(FileNotFoundError):
            add_data_to_project(
                session,
                [sac_file_good, non_existent_file],
                data_type=DataType.SAC,
            )

        datasource = session.exec(select(AimbatDataSource.sourcename)).all()
        assert (
            len(datasource) == 0
        ), "Expected no data sources to be added when an error occurs."

    def test_add_sac_file_with_missing_pick(
        self, sac_file_good: Path, session: Session
    ) -> None:
        """Verifies that adding a SAC file missing required pick information raises ValidationError.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            session (Session): Database session.
        """
        sac = SAC.from_file(sac_file_good)
        sac.timestamps.t0 = None
        sac.write(sac_file_good)
        with pytest.raises(ValidationError):
            add_data_to_project(
                session,
                [sac_file_good],
                data_type=DataType.SAC,
            )

    def test_dry_run_all_new(
        self,
        multi_event_data: list[Path],
        session: Session,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Verifies dry run behaviour when all data is new.

        Args:
            multi_event_data (list[Path]): List of paths to SAC files.
            session (Session): Database session.
            capsys (pytest.CaptureFixture): Fixture to capture stdout/stderr.
        """
        add_data_to_project(
            session,
            multi_event_data,
            data_type=DataType.SAC,
            dry_run=True,
        )

        datasource = session.exec(select(AimbatDataSource.sourcename)).all()
        assert len(datasource) == 0, "Expected no data sources after dry run."

        captured = capsys.readouterr()
        assert "Dry Run: Data to be added" in captured.out
        n = len(multi_event_data)
        assert f"{n} seismogram(s) added, 0 skipped" in captured.out
        assert "0 skipped" in captured.out

    def test_dry_run_all_skipped(
        self,
        multi_event_data: list[Path],
        session: Session,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Verifies dry run behaviour when all data already exists (should be skipped).

        Args:
            multi_event_data (list[Path]): List of paths to SAC files.
            session (Session): Database session.
            capsys (pytest.CaptureFixture): Fixture to capture stdout/stderr.
        """
        add_data_to_project(
            session,
            multi_event_data,
            data_type=DataType.SAC,
        )
        capsys.readouterr()

        add_data_to_project(
            session,
            multi_event_data,
            data_type=DataType.SAC,
            dry_run=True,
        )

        captured = capsys.readouterr()
        assert "Dry Run: Data to be added" in captured.out
        n = len(multi_event_data)
        assert f"0 station(s) added, {n} skipped" in captured.out
        assert f"0 event(s) added, {n} skipped" in captured.out
        assert f"0 seismogram(s) added, {n} skipped" in captured.out


class TestGetDataSources:
    @pytest.fixture
    def session(self, loaded_session: Session) -> Generator[Session, None, None]:
        """Provides a database session with pre-loaded data sources for tests.

        Args:
            loaded_session (Session): A SQLAlchemy session fixture with pre-loaded data sources.
        """
        yield loaded_session

    def test_get_data_sources_for_default_event(self, session: Session) -> None:
        """Verifies that get_data_sources returns the expected data sources.

        Args:
            session (Session): Database session.
        """
        default_event = get_default_event(session)
        assert default_event is not None
        data_sources = get_data_for_event(session, default_event)
        assert len(data_sources) != 0, "Expected data sources for the default event."
        assert all(
            isinstance(ds, AimbatDataSource) for ds in data_sources
        ), "expected all items to be AimbatDataSource instances"

    def test_dump_data_table_to_json(self, session: Session) -> None:
        """Verifies that dump_data_table_to_json returns a JSON string with expected content.

        Args:
            session (Session): Database session.
        """
        json_str = dump_data_table_to_json(session)
        json_data = json.loads(json_str)
        assert isinstance(json_data, list), "Expected JSON data to be a list."

        expected_ids = map(str, session.exec(select(AimbatDataSource.id)).all())
        returned_ids = [item["id"] for item in json_data]
        assert set(expected_ids) == set(returned_ids), "Expected IDs to match."


# ===================================================================
# Engine-level tests (add_data_to_project with engine fixture)
# ===================================================================


class TestAddDataSac:
    """Tests for add_data_to_project with SAC data."""

    def test_creates_station_event_seismogram_and_datasource(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that a SAC import creates all four entity types.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [sac_file_good], DataType.SAC)

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 1
            assert len(session.exec(select(AimbatEvent)).all()) == 1
            assert len(session.exec(select(AimbatSeismogram)).all()) == 1
            assert len(session.exec(select(AimbatDataSource)).all()) == 1

    def test_duplicate_import_does_not_create_duplicates(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that importing the same SAC file twice does not duplicate records.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [sac_file_good], DataType.SAC)
            add_data_to_project(session, [sac_file_good], DataType.SAC)

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 1
            assert len(session.exec(select(AimbatEvent)).all()) == 1
            assert len(session.exec(select(AimbatSeismogram)).all()) == 1
            assert len(session.exec(select(AimbatDataSource)).all()) == 1


class TestAddDataJsonStation:
    """Tests for add_data_to_project with JSON_STATION data."""

    def test_creates_station_only(self, engine: Engine, station_json: Path) -> None:
        """Verifies that a JSON_STATION import creates only a station record.

        Args:
            engine: In-memory SQLAlchemy Engine.
            station_json: Path to a valid JSON station file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [station_json], DataType.JSON_STATION)

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 1
            assert len(session.exec(select(AimbatEvent)).all()) == 0
            assert len(session.exec(select(AimbatSeismogram)).all()) == 0
            assert len(session.exec(select(AimbatDataSource)).all()) == 0

    def test_station_fields_match_json(
        self, engine: Engine, station_json: Path
    ) -> None:
        """Verifies that imported station fields match the JSON values.

        Args:
            engine: In-memory SQLAlchemy Engine.
            station_json: Path to a valid JSON station file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [station_json], DataType.JSON_STATION)

        with Session(engine) as session:
            station = session.exec(select(AimbatStation)).one()
            assert station.name == _STATION_DATA["name"]
            assert station.network == _STATION_DATA["network"]
            assert station.location == _STATION_DATA["location"]
            assert station.channel == _STATION_DATA["channel"]
            assert station.latitude == _STATION_DATA["latitude"]


class TestAddDataJsonEvent:
    """Tests for add_data_to_project with JSON_EVENT data."""

    def test_creates_event_only(self, engine: Engine, event_json: Path) -> None:
        """Verifies that a JSON_EVENT import creates only an event record.

        Args:
            engine: In-memory SQLAlchemy Engine.
            event_json: Path to a valid JSON event file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [event_json], DataType.JSON_EVENT)

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 0
            assert len(session.exec(select(AimbatEvent)).all()) == 1
            assert len(session.exec(select(AimbatSeismogram)).all()) == 0
            assert len(session.exec(select(AimbatDataSource)).all()) == 0

    def test_event_fields_match_json(self, engine: Engine, event_json: Path) -> None:
        """Verifies that imported event fields match the JSON values.

        Args:
            engine: In-memory SQLAlchemy Engine.
            event_json: Path to a valid JSON event file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [event_json], DataType.JSON_EVENT)

        with Session(engine) as session:
            event = session.exec(select(AimbatEvent)).one()
            assert event.time == Timestamp("2020-01-01T00:00:00Z")
            assert event.latitude == _EVENT_DATA["latitude"]
            assert event.longitude == _EVENT_DATA["longitude"]
            assert event.depth == _EVENT_DATA["depth"]

    def test_event_has_parameters(self, engine: Engine, event_json: Path) -> None:
        """Verifies that the imported event has initialised parameters.

        Args:
            engine: In-memory SQLAlchemy Engine.
            event_json: Path to a valid JSON event file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [event_json], DataType.JSON_EVENT)

        with Session(engine) as session:
            event = session.exec(select(AimbatEvent)).one()
            assert event.parameters is not None


class TestUuidValidation:
    """Tests for early UUID validation in add_data_to_project."""

    def test_invalid_station_id_raises_value_error(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that a non-existent station UUID raises ValueError before the import loop.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            with pytest.raises(ValueError, match="No station found"):
                add_data_to_project(
                    session,
                    [sac_file_good],
                    DataType.SAC,
                    station_id=uuid.uuid4(),
                )

    def test_invalid_event_id_raises_value_error(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that a non-existent event UUID raises ValueError before the import loop.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            with pytest.raises(ValueError, match="No event found"):
                add_data_to_project(
                    session,
                    [sac_file_good],
                    DataType.SAC,
                    event_id=uuid.uuid4(),
                )

    def test_invalid_uuid_does_not_modify_database(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that a failed UUID check leaves the database unchanged.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            with pytest.raises(ValueError):
                add_data_to_project(
                    session,
                    [sac_file_good],
                    DataType.SAC,
                    station_id=uuid.uuid4(),
                )

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 0
            assert len(session.exec(select(AimbatEvent)).all()) == 0


class TestCombinedSacAndJsonStation:
    """Tests for combining SAC seismogram data with a JSON-imported station."""

    def test_sac_with_station_id_links_to_json_station(
        self, engine: Engine, sac_file_good: Path, station_json: Path
    ) -> None:
        """Verifies that a SAC import with station_id links to the pre-existing station.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
            station_json: Path to a valid JSON station file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [station_json], DataType.JSON_STATION)
            station = session.exec(select(AimbatStation)).one()
            station_id = station.id

        with Session(engine) as session:
            add_data_to_project(
                session, [sac_file_good], DataType.SAC, station_id=station_id
            )

        with Session(engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).one()
            assert seismogram.station_id == station_id

    def test_sac_with_station_id_does_not_create_extra_station(
        self, engine: Engine, sac_file_good: Path, station_json: Path
    ) -> None:
        """Verifies that the SAC file's embedded station data is ignored when station_id is provided.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
            station_json: Path to a valid JSON station file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [station_json], DataType.JSON_STATION)
            station = session.exec(select(AimbatStation)).one()
            station_id = station.id

        with Session(engine) as session:
            add_data_to_project(
                session, [sac_file_good], DataType.SAC, station_id=station_id
            )

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 1


class TestCombinedSacAndJsonEvent:
    """Tests for combining SAC seismogram data with a JSON-imported event."""

    def test_sac_with_event_id_links_to_json_event(
        self, engine: Engine, sac_file_good: Path, event_json: Path
    ) -> None:
        """Verifies that a SAC import with event_id links to the pre-existing event.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
            event_json: Path to a valid JSON event file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [event_json], DataType.JSON_EVENT)
            event = session.exec(select(AimbatEvent)).one()
            event_id = event.id

        with Session(engine) as session:
            add_data_to_project(
                session, [sac_file_good], DataType.SAC, event_id=event_id
            )

        with Session(engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).one()
            assert seismogram.event_id == event_id

    def test_sac_with_event_id_does_not_create_extra_event(
        self, engine: Engine, sac_file_good: Path, event_json: Path
    ) -> None:
        """Verifies that the SAC file's embedded event data is ignored when event_id is provided.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
            event_json: Path to a valid JSON event file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [event_json], DataType.JSON_EVENT)
            event = session.exec(select(AimbatEvent)).one()
            event_id = event.id

        with Session(engine) as session:
            add_data_to_project(
                session, [sac_file_good], DataType.SAC, event_id=event_id
            )

        with Session(engine) as session:
            assert len(session.exec(select(AimbatEvent)).all()) == 1


class TestDryRun:
    """Tests for the dry_run option."""

    def test_dry_run_does_not_persist_changes(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that dry_run=True rolls back all changes.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [sac_file_good], DataType.SAC, dry_run=True)

        with Session(engine) as session:
            assert len(session.exec(select(AimbatDataSource)).all()) == 0
            assert len(session.exec(select(AimbatSeismogram)).all()) == 0
            assert len(session.exec(select(AimbatStation)).all()) == 0
            assert len(session.exec(select(AimbatEvent)).all()) == 0
