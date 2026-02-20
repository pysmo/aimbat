from sqlalchemy import Engine
from aimbat.app import app
from pathlib import Path
from sqlmodel import Session
import aimbat.core._project as project
import pytest


class TestProjectBase:
    """Base class for project tests."""


class TestProjectExists(TestProjectBase):
    def test_lib_project_exists_if_false(
        self, fixture_empty_db: tuple[Engine, Session]
    ) -> None:

        engine, _ = fixture_empty_db

        assert project._project_exists(engine) is False

    def test_lib_project_exists_if_true(
        self, fixture_empty_db: tuple[Engine, Session]
    ) -> None:
        engine, _ = fixture_empty_db
        project.create_project(engine)
        assert project._project_exists(engine) is True


class TestProjectCreate(TestProjectBase):
    @pytest.mark.dependency(name="create_project")
    def test_lib_create_project(self, fixture_empty_db: tuple[Engine, Session]) -> None:
        engine, _ = fixture_empty_db
        assert project._project_exists(engine) is False
        project.create_project(engine)
        assert project._project_exists(engine) is True

    def test_lib_create_project_when_one_exists(
        self, fixture_empty_db: tuple[Engine, Session]
    ) -> None:
        engine, _ = fixture_empty_db
        assert project._project_exists(engine) is False
        project.create_project(engine)
        assert project._project_exists(engine) is True
        with pytest.raises(RuntimeError):
            project.create_project(engine)

    def test_cli_create_project(self, fixture_empty_db: tuple[Engine, Session]) -> None:
        engine, _ = fixture_empty_db
        assert project._project_exists(engine) is False
        with pytest.raises(SystemExit) as excinfo:
            app(["project", "create"])
        assert excinfo.value.code == 0
        assert project._project_exists(engine) is True


class TestProjectDelete(TestProjectBase):
    def test_lib_delete_project_file(
        self, fixture_session_with_project_file: tuple[Engine, Session, Path]
    ) -> None:

        engine, _, _ = fixture_session_with_project_file

        assert project._project_exists(engine) is True

        project.delete_project(engine)
        assert project._project_exists(engine) is False

    def test_lib_delete_project(
        self, fixture_engine_session_with_project: tuple[Engine, Session]
    ) -> None:
        engine, _ = fixture_engine_session_with_project

        assert project._project_exists(engine) is True

        project.delete_project(engine)
        assert project._project_exists(engine) is False

    def test_cli_delete_project(
        self, fixture_engine_session_with_project: tuple[Engine, Session]
    ) -> None:
        engine, _ = fixture_engine_session_with_project
        assert project._project_exists(engine) is True

        with pytest.raises(SystemExit) as excinfo:
            app(["project", "delete"])
        assert excinfo.value.code == 0
        assert project._project_exists(engine) is False


class TestProjectTable(TestProjectBase):
    def test_lib_print_project_info_no_project(
        self, fixture_empty_db: tuple[Engine, Session]
    ) -> None:
        engine, _ = fixture_empty_db
        with pytest.raises(RuntimeError):
            project.print_project_info(engine)

    def test_lib_print_project_info_with_empty_project(
        self,
        fixture_engine_session_with_project: tuple[Engine, Session],
        capsys: pytest.CaptureFixture,
    ) -> None:
        engine, _ = fixture_engine_session_with_project
        project.print_project_info(engine)
        captured = capsys.readouterr()
        assert "Project Info" in captured.out
        assert "None" in captured.out

    def test_lib_print_project_info_with_active_event(
        self,
        fixture_engine_session_with_active_event: tuple[Engine, Session],
        capsys: pytest.CaptureFixture,
    ) -> None:
        engine, _ = fixture_engine_session_with_active_event
        project.print_project_info(engine)
        captured = capsys.readouterr()
        assert "Project Info" in captured.out
        assert "(3/0)" in captured.out

    def test_cli_print_project_info_with_active_event(
        self,
        fixture_engine_session_with_active_event: tuple[Engine, Session],
        capsys: pytest.CaptureFixture,
    ) -> None:
        engine, _ = fixture_engine_session_with_active_event
        assert project._project_exists(engine) is True

        with pytest.raises(SystemExit) as excinfo:
            app(["project", "info"])
        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        assert "Project Info" in captured.out
        assert "(3/0)" in captured.out
