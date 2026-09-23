"""Do some tests with a real file-based database.

This is to verify that the project creation and deletion works as expected.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from aimbat.core import create_project, delete_project
from aimbat.core._project import _project_exists


def _triggers(engine: Engine) -> list[str]:
    """Names of the triggers the database currently has."""
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'trigger'")
        ).all()
    return [name for (name,) in rows]


class TestProjectLifecycle:
    """Integration tests for core project management functions."""

    @pytest.fixture
    def engine(self, engine_from_file: Engine) -> Generator[Engine]:
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
        assert _project_exists(engine) is False, (
            "expected _project_exists() to return False at the start of the test"
        )

        create_project(engine)

        assert db_path.exists(), (
            "expected project file to be created after calling create_project()"
        )
        assert _project_exists(engine) is True, (
            "expected _project_exists() to return True after creating project"
        )

    def test_create_if_one_exists(self, engine: Engine) -> None:
        """Verifies that creating a project fails if one already exists.

        Args:
            engine (Engine): The SQLAlchemy engine.
        """
        assert not _project_exists(engine), (
            "expected no project at the start of the test"
        )
        create_project(engine)
        assert _project_exists(engine), (
            "expected project to exist after calling create_project()"
        )

        with pytest.raises(RuntimeError):
            create_project(engine)

    def test_delete_project(self, engine: Engine) -> None:
        """Verifies that an existing project can be deleted.

        Args:
            engine (Engine): The SQLAlchemy engine.
        """
        assert not _project_exists(engine), (
            "expected no project at the start of the test"
        )
        create_project(engine)
        assert _project_exists(engine), (
            "expected project to exist after calling create_project()"
        )

        delete_project(engine)
        assert not _project_exists(engine), (
            "expected no project after calling delete_project()"
        )

    def test_delete_project_removes_wal_and_shm_sidecars(
        self, engine: Engine, db_path: Path
    ) -> None:
        """Verifies that `-wal`/`-shm` sidecar files are removed alongside the database.

        Args:
            engine (Engine): The SQLAlchemy engine.
            db_path (Path): The path to the project database file.
        """
        create_project(engine)
        wal_path = db_path.with_name(db_path.name + "-wal")
        shm_path = db_path.with_name(db_path.name + "-shm")
        wal_path.touch()
        shm_path.touch()

        delete_project(engine)

        assert not wal_path.exists(), "expected -wal sidecar to be removed"
        assert not shm_path.exists(), "expected -shm sidecar to be removed"

    def test_delete_project_refuses_suspicious_path(
        self, engine: Engine, db_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies `delete_project` refuses to unlink a path that looks unsafe.

        Args:
            engine (Engine): The SQLAlchemy engine.
            db_path (Path): The path to the project database file.
            monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.
        """
        create_project(engine)
        monkeypatch.setattr(Path, "home", staticmethod(lambda: db_path.resolve()))

        with pytest.raises(RuntimeError, match="suspicious"):
            delete_project(engine)

        assert db_path.exists(), "expected the project file to survive the refusal"

    def test_failed_trigger_creation_leaves_no_project(
        self, engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies a failure partway through `create_project` rolls the whole lot back.

        Regression test: tables, triggers and the Alembic stamp used to be
        three separate transactions, so a failure during trigger creation
        left a database with tables but no quality invalidation - dead
        silently, and indistinguishable afterwards from a complete project.

        Args:
            engine (Engine): The SQLAlchemy engine.
            monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.
        """
        import aimbat.core._project as project

        monkeypatch.setattr(
            project, "_null_quality_trigger", lambda *args: "NOT VALID SQL"
        )

        with pytest.raises(OperationalError):
            create_project(engine)

        assert not _project_exists(engine), (
            "expected no tables to survive a failed create_project()"
        )
        assert not _triggers(engine), "expected no triggers to survive either"

        monkeypatch.undo()
        create_project(engine)
        assert _project_exists(engine), "expected a retry to succeed"

    def test_failed_stamp_leaves_no_project(
        self, engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies the Alembic stamp is inside the same transaction as the schema.

        Args:
            engine (Engine): The SQLAlchemy engine.
            monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.
        """
        import aimbat.core._migrations as migrations

        def fail(bind: object) -> None:
            raise RuntimeError("stamping failed")

        monkeypatch.setattr(migrations, "stamp_head", fail)

        with pytest.raises(RuntimeError, match="stamping failed"):
            create_project(engine)

        assert not _project_exists(engine), (
            "expected no tables to survive a failed stamp"
        )

    def test_delete_project_when_there_is_none(self, engine: Engine) -> None:
        """Verifies that attempting to delete a non-existent project raises an error.

        Args:
            engine (Engine): The SQLAlchemy engine.
        """
        assert not _project_exists(engine), (
            "expected no project at the start of the test"
        )
        with pytest.raises(RuntimeError):
            delete_project(engine)


class TestPrintProjectInfo:
    """Tests for printing project summary information."""

    def test_raises_when_no_project(
        self, engine_from_file: Engine, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verifies that a RuntimeError is raised when no project exists.

        Args:
            engine_from_file: A SQLAlchemy Engine connected to an empty file database.
            capsys: The pytest capsys fixture.
        """
        with pytest.raises(RuntimeError):
            delete_project(engine_from_file)
