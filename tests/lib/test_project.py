from pathlib import Path
from click.testing import CliRunner
from importlib import reload
import pytest
import platform


class TestLibProject:

    def test_project(self) -> None:

        from aimbat.lib import project

        # reload(project)
        project_file = project.AIMBAT_PROJECT

        assert Path(project_file).exists() is False

        with pytest.raises(FileNotFoundError):
            project.project_info()

        project.project_new()
        assert Path(project_file).exists() is True

        with pytest.raises(FileExistsError):
            project.project_new()

        # TODO: change this when info is implemented
        with pytest.raises(NotImplementedError):
            project.project_info()

        # HACK - this does run on windows, but not on
        # github actions for some reason.
        if platform.system() != "Windows":
            project.project_del()
            assert Path(project_file).exists() is False

            with pytest.raises(FileNotFoundError):
                project.project_del()


class TestCliProject:

    def test_project(self) -> None:
        """Test AIMBAT cli with project subcommand."""

        from aimbat.lib import project

        reload(project)

        assert not Path.exists(Path(project.AIMBAT_PROJECT))

        runner = CliRunner()
        result = runner.invoke(project.cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(project.cli, ["new"])
        assert result.exit_code == 0
        assert "Created new AIMBAT project" in result.output
        assert Path.exists(Path(project.AIMBAT_PROJECT))

        result = runner.invoke(project.cli, ["new"])
        assert result.exit_code == 0
        assert (
            "Unable to create a new project: found existing AIMBAT_PROJECT"
            in result.output
        )

        # TODO - info not implemented yet
        result = runner.invoke(project.cli, ["info"])
        assert result.exit_code == 1

        # HACK - this does run on windows, but not on
        # github actions for some reason.
        if platform.system() != "Windows":
            result = runner.invoke(project.cli, ["del", "--yes"])
            assert result.exit_code == 0
            assert not Path.exists(Path(project.AIMBAT_PROJECT))

            result = runner.invoke(project.cli, ["del", "--yes"])
            assert result.exit_code == 0
            assert "Unable to delete project: AIMBAT_PROJECT=" in result.output

            result = runner.invoke(project.cli, ["info"])
            assert result.exit_code == 0
            assert "Unable to show info: AIMBAT_PROJECT=" in result.output
