from aimbat.app import app
from pathlib import Path
from sqlmodel import Session
import aimbat.lib.project as project
import pytest


class TestProjectBase:
    """Base class for project tests."""


class TestProjectExists(TestProjectBase):
    def test_lib_project_exists_if_false(self, fixture_session_empty: Session) -> None:
        assert project._project_exists() is False

    def test_lib_project_exists_if_true(self, fixture_session_empty: Session) -> None:
        project.create_project()
        assert project._project_exists() is True


class TestProjectCreate(TestProjectBase):
    @pytest.mark.dependency(name="create_project")
    def test_lib_create_project(self, fixture_session_empty: Session) -> None:
        assert project._project_exists() is False
        project.create_project()
        assert project._project_exists() is True

    def test_lib_create_project_when_one_exists(
        self, fixture_session_empty: Session
    ) -> None:
        assert project._project_exists() is False
        project.create_project()
        assert project._project_exists() is True
        with pytest.raises(RuntimeError):
            project.create_project()

    def test_cli_create_project(self, fixture_session_empty: Session) -> None:
        assert project._project_exists() is False
        with pytest.raises(SystemExit) as excinfo:
            app(["project", "create"])
        assert excinfo.value.code == 0
        assert project._project_exists() is True


class TestProjectDelete(TestProjectBase):
    def test_lib_delete_project_file(
        self, fixture_session_with_project_file: tuple[Session, Path]
    ) -> None:
        assert project._project_exists() is True

        project.delete_project()
        assert project._project_exists() is False

    def test_lib_delete_project(self, fixture_session_with_project: Session) -> None:
        assert project._project_exists() is True

        project.delete_project()
        assert project._project_exists() is False

    def test_cli_delete_project(self, fixture_session_with_project: Session) -> None:
        assert project._project_exists() is True

        with pytest.raises(SystemExit) as excinfo:
            app(["project", "delete"])
        assert excinfo.value.code == 0
        assert project._project_exists() is False


class TestProjectTable(TestProjectBase):
    def test_lib_print_project_info_no_project(
        self, fixture_session_empty: tuple[Path, Session]
    ) -> None:
        with pytest.raises(RuntimeError):
            project.print_project_info()

    def test_lib_print_project_info_with_empty_project(
        self,
        fixture_session_with_project: Session,
        capsys: pytest.CaptureFixture,
    ) -> None:
        project.print_project_info()
        captured = capsys.readouterr()
        assert "Project Info" in captured.out
        assert "None" in captured.out

    def test_lib_print_project_info_with_active_event(
        self, fixture_session_with_active_event: Session, capsys: pytest.CaptureFixture
    ) -> None:
        project.print_project_info()
        captured = capsys.readouterr()
        assert "Project Info" in captured.out
        assert "(3/0)" in captured.out

    def test_cli_print_project_info_with_active_event(
        self, fixture_session_with_active_event: Session, capsys: pytest.CaptureFixture
    ) -> None:
        assert project._project_exists() is True

        with pytest.raises(SystemExit) as excinfo:
            app(["project", "info"])
        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        assert "Project Info" in captured.out
        assert "(3/0)" in captured.out
