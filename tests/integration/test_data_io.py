"""Integration tests for adding data (SAC files) to the project."""

import pytest
import json
from aimbat.core import (
    add_data_to_project,
    get_data_for_active_event,
    print_data_table,
    dump_data_table_to_json,
)
from aimbat.aimbat_types import DataType
from aimbat.models import AimbatDataSource, AimbatEvent, AimbatSeismogram
from pysmo.classes import SAC
from pathlib import Path
from sqlmodel import Session, select
from pydantic import ValidationError
from collections.abc import Generator


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
                datatype=DataType.SAC,
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
            datatype=DataType.SAC,
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
                datatype=DataType.SAC,
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
                datatype=DataType.SAC,
            )

        # Verify that the valid file was not added due to the error
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
                datatype=DataType.SAC,
            )

    def test_dry_run_all_new(
        self,
        multi_event_data: list[Path],
        session: Session,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Verifies dry run behavior when all data is new.

        Args:
            multi_event_data (list[Path]): List of paths to SAC files.
            session (Session): Database session.
            capsys (pytest.CaptureFixture): Fixture to capture stdout/stderr.
        """
        add_data_to_project(
            session,
            multi_event_data,
            datatype=DataType.SAC,
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
        """Verifies dry run behavior when all data already exists (should be skipped).

        Args:
            multi_event_data (list[Path]): List of paths to SAC files.
            session (Session): Database session.
            capsys (pytest.CaptureFixture): Fixture to capture stdout/stderr.
        """
        add_data_to_project(
            session,
            multi_event_data,
            datatype=DataType.SAC,
        )
        capsys.readouterr()  # discard output from the real add

        add_data_to_project(
            session,
            multi_event_data,
            datatype=DataType.SAC,
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

    def test_get_data_sources_for_active_event(self, session: Session) -> None:
        """Verifies that get_data_sources returns the expected data sources.

        Args:
            session (Session): Database session.
        """

        data_sources = get_data_for_active_event(session)
        assert len(data_sources) != 0, "Expected data sources for the active event."
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

    def test_print_data_table_for_all_events(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        """Verifies that get_data_sources prints the expected table output.

        Args:
            session (Session): Database session.
            capsys (pytest.CaptureFixture): Fixture to capture stdout/stderr.
        """
        print_data_table(session, short=False, all_events=True)

        expected_ids = session.exec(select(AimbatDataSource.id)).all()

        captured = capsys.readouterr()
        assert "Data sources for all events" in captured.out
        for id in expected_ids:
            assert (
                str(id) in captured.out
            ), "expected data source ID to be in the output table"

    def test_print_data_table_for_all_events_short(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        """Verifies that get_data_sources prints the expected table output.

        Args:
            session (Session): Database session.
            capsys (pytest.CaptureFixture): Fixture to capture stdout/stderr.
        """

        expected_ids = session.exec(select(AimbatDataSource.id)).all()

        print_data_table(session, short=True, all_events=True)

        captured = capsys.readouterr()
        assert "Data sources for all events" in captured.out
        for id in expected_ids:
            assert (
                str(id)[:2] in captured.out
            ), "expected data source ID to be in the output table"

    def test_print_data_table_for_active_event(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        """Verifies that get_data_sources prints the expected table output.

        Args:
            session (Session): Database session.
            capsys (pytest.CaptureFixture): Fixture to capture stdout/stderr.
        """

        # AimbatSeismogram has external_id of datasource and event:
        statement = (
            select(AimbatDataSource.id)
            .join(AimbatSeismogram)
            .join(AimbatEvent)
            .where(AimbatEvent.active == 1)
        )
        expected_ids = session.exec(statement).all()

        print_data_table(session, short=False, all_events=False)

        captured = capsys.readouterr()
        assert "Data sources for event" in captured.out
        for id in expected_ids:
            assert (
                str(id) in captured.out
            ), "expected data source ID to be in the output table"

    def test_print_data_table_for_active_event_short(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        """Verifies that get_data_sources prints the expected table output.

        Args:
            session (Session): Database session.
            capsys (pytest.CaptureFixture): Fixture to capture stdout/stderr.
        """

        # AimbatSeismogram has external_id of datasource and event:
        statement = (
            select(AimbatDataSource.id)
            .join(AimbatSeismogram)
            .join(AimbatEvent)
            .where(AimbatEvent.active == 1)
        )
        expected_ids = session.exec(statement).all()

        print_data_table(session, short=True, all_events=False)

        captured = capsys.readouterr()
        assert "Data sources for event" in captured.out
        for id in expected_ids:
            assert (
                str(id)[:2] in captured.out
            ), "expected data source ID to be in the output table"
