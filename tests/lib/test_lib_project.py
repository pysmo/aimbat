from pathlib import Path
import pytest
import platform


class TestLibProject:
    def test_project(self) -> None:
        from aimbat.lib import project

        project_file = project.AIMBAT_PROJECT

        assert Path(project_file).exists() is False

        with pytest.raises(FileNotFoundError):
            project.project_print_info()

        project.project_new()
        assert Path(project_file).exists() is True

        with pytest.raises(FileExistsError):
            project.project_new()

        project.project_print_info()

        # HACK - this does run on windows, but not on
        # github actions for some reason.
        if platform.system() != "Windows":
            project.project_del()
            assert Path(project_file).exists() is False

            with pytest.raises(FileNotFoundError):
                project.project_del()
