from pathlib import Path
from importlib import reload
from sqlmodel import Session
import aimbat.lib.project as project
import pytest


class TestProjectBase:
    @pytest.fixture(autouse=True)
    def reload_modules(self, test_db: tuple[Path, Session]) -> None:
        reload(project)


class TestProjectExists(TestProjectBase):
    def test_lib_project_exists_if_false(self, test_db: tuple[Path, Session]) -> None:
        assert project._project_exists() is False

    def test_lib_project_exists_if_true(self, test_db: tuple[Path, Session]) -> None:
        project.create_project()
        assert project._project_exists() is True


class TestProjectCreate(TestProjectBase):
    @pytest.mark.dependency(name="create_project")
    def test_lib_create_project(self, test_db: tuple[Path, Session]) -> None:
        assert project._project_exists() is False
        project.create_project()
        assert project._project_exists() is True

    def test_lib_create_project_when_one_exists(
        self, test_db: tuple[Path, Session]
    ) -> None:
        assert project._project_exists() is False
        project.create_project()
        assert project._project_exists() is True
        with pytest.raises(RuntimeError):
            project.create_project()

    def test_cli_create_project(self, test_db: tuple[Path, Session]) -> None:
        from aimbat.app import app

        assert project._project_exists() is False
        app(["project", "create"])
        assert project._project_exists() is True


class TestProjectFileFromEngine(TestProjectBase):
    def test_lib_project_file_from_engine(
        self, test_db_with_project: tuple[Path, Session]
    ) -> None:
        reload(project)
        assert project._project_exists() is True
        test_db_file = test_db_with_project[0]
        assert project._project_file_from_engine() == test_db_file


class TestProjectDelete(TestProjectBase):
    def test_lib_delete_project(
        self, test_db_with_project: tuple[Path, Session]
    ) -> None:
        reload(project)
        assert project._project_exists() is True

        project.delete_project()
        assert project._project_exists() is False

    def test_cli_delete_project(
        self, test_db_with_project: tuple[Path, Session]
    ) -> None:
        reload(project)
        from aimbat.app import app

        assert project._project_exists() is True

        app(["project", "delete"])
        assert project._project_exists() is False


class TestProjectTable(TestProjectBase):
    def test_lib_print_project_info_no_project(
        self, test_db: tuple[Path, Session]
    ) -> None:
        with pytest.raises(RuntimeError):
            project.print_project_info()

    def test_lib_print_project_info_with_empty_project(
        self, test_db_with_project: tuple[Path, Session], capsys: pytest.CaptureFixture
    ) -> None:
        reload(project)
        project.print_project_info()
        captured = capsys.readouterr()
        assert "Project Info" in captured.out
        assert "None" in captured.out

    def test_lib_print_project_info_with_active_event(
        self,
        test_db_with_active_event: tuple[Path, Session],
        capsys: pytest.CaptureFixture,
    ) -> None:
        reload(project)
        project.print_project_info()
        captured = capsys.readouterr()
        assert "Project Info" in captured.out
        assert "(3/0)" in captured.out

    def test_cli_print_project_info_with_active_event(
        self,
        test_db_with_active_event: tuple[Path, Session],
        capsys: pytest.CaptureFixture,
    ) -> None:
        reload(project)
        from aimbat.app import app

        assert project._project_exists() is True

        app(["project", "info"])
        captured = capsys.readouterr()
        assert "Project Info" in captured.out
        assert "(3/0)" in captured.out
