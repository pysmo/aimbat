"""Do some tests with a real file-based database.

This is to verify that the project creation and deletion works as expected.
"""

import pytest
from pathlib import Path
from aimbat.core import create_project, delete_project
from aimbat.core._project import _project_exists, print_project_info
from collections.abc import Generator
from sqlalchemy import Engine


class TestProjectLifecycle:
    """Integration tests for core project management functions."""

    @pytest.fixture
    def engine(self, engine_from_file: Engine) -> Generator[Engine, None, None]:
        yield engine_from_file

    def test_create(self, engine: Engine, db_path: Path) -> None:
        """Verifies that a new project can be created successfully.

        This test ensures that `create_project` creates the database file and that `_project_exists`
        correctly reflects the project's existence.

        Args:
            engine (Engine): The SQLAlchemy engine.
            project_file (Path): The path to the expected project database file.
        """
        assert not db_path.exists(), "expected no project file at the start of the test"
        assert (
            _project_exists(engine) is False
        ), "expected _project_exists() to return False at the start of the test"

        create_project(engine)

        assert (
            db_path.exists()
        ), "expected project file to be created after calling create_project()"
        assert (
            _project_exists(engine) is True
        ), "expected _project_exists() to return True after creating project"

    def test_create_if_one_exists(self, engine: Engine) -> None:
        """Verifies that creating a project fails if one already exists.

        Args:
            engine (Engine): The SQLAlchemy engine.
        """
        assert not _project_exists(
            engine
        ), "expected no project at the start of the test"
        create_project(engine)
        assert _project_exists(
            engine
        ), "expected project to exist after calling create_project()"

        with pytest.raises(RuntimeError):
            create_project(engine)

    def test_delete_project(self, engine: Engine) -> None:
        """Verifies that an existing project can be deleted.

        Args:
            engine (Engine): The SQLAlchemy engine.
        """
        assert not _project_exists(
            engine
        ), "expected no project at the start of the test"
        create_project(engine)
        assert _project_exists(
            engine
        ), "expected project to exist after calling create_project()"

        delete_project(engine)
        assert not _project_exists(
            engine
        ), "expected no project after calling delete_project()"

    def test_delete_project_when_there_is_none(self, engine: Engine) -> None:
        """Verifies that attempting to delete a non-existent project raises an error.

        Args:
            engine (Engine): The SQLAlchemy engine.
        """
        assert not _project_exists(
            engine
        ), "expected no project at the start of the test"
        with pytest.raises(RuntimeError):
            delete_project(engine)


class TestPrintProjectInfo:
    """Tests for printing project summary information."""

    def test_raises_when_no_project(
        self, engine_from_file: Engine, capsys: pytest.CaptureFixture
    ) -> None:
        """Verifies that a RuntimeError is raised when no project exists.

        Args:
            engine_from_file: A SQLAlchemy Engine connected to an empty file database.
            capsys: The pytest capsys fixture.
        """
        with pytest.raises(RuntimeError):
            print_project_info(engine_from_file)

    def test_with_empty_project(
        self, patched_engine: Engine, capsys: pytest.CaptureFixture
    ) -> None:
        """Verifies that output is produced for a project with no data or active event.

        Args:
            patched_engine: The monkeypatched SQLAlchemy Engine.
            capsys: The pytest capsys fixture.
        """
        print_project_info(patched_engine)
        assert len(capsys.readouterr().out) > 0

    def test_with_data_and_active_event(
        self, loaded_engine: Engine, capsys: pytest.CaptureFixture
    ) -> None:
        """Verifies that output is produced for a project with data and an active event.

        Args:
            loaded_engine: The monkeypatched SQLAlchemy Engine with data loaded.
            capsys: The pytest capsys fixture.
        """
        print_project_info(loaded_engine)
        assert len(capsys.readouterr().out) > 0
