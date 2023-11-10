from pathlib import Path
from click.testing import CliRunner
from importlib import reload
import pytest


@pytest.mark.usefixtures("mock_project_env")
class TestProject:
    def test_lib_project(self, tmp_project_filename, tmp_db_engine) -> None:  # type: ignore
        from aimbat.lib import project

        # try deleting a project when there is none
        assert not tmp_project_filename.exists()
        with pytest.raises(FileNotFoundError):
            project.project_del(tmp_project_filename)

        # try getting project info when there is no project
        with pytest.raises(FileNotFoundError):
            project.project_info(tmp_project_filename)

        # create project
        assert not tmp_project_filename.exists()
        project.project_new(tmp_project_filename, tmp_db_engine)
        assert tmp_project_filename.exists()

        # try creating again
        with pytest.raises(FileExistsError):
            project.project_new(tmp_project_filename, tmp_db_engine)

        # TODO: change this when info is implemented
        with pytest.raises(NotImplementedError):
            project.project_info(tmp_project_filename)

        # delete project
        project.project_del(tmp_project_filename)
        assert not tmp_project_filename.exists()

    @pytest.mark.depends(
        depends=["/tests/test_cli.py::test_cli", "TestProject.test_lib_project"],
        scope="session",
    )
    def test_cli_project(self) -> None:
        """Test AIMBAT cli with project subcommand."""

        from aimbat.lib import defaults, project, db

        reload(db)
        reload(project)
        reload(defaults)

        project_file = Path(project.AIMBAT_PROJECT)
        assert not project_file.exists()

        runner = CliRunner()
        result = runner.invoke(project.cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(project.cli, ["new"])
        assert result.exit_code == 0
        assert project_file.exists()
        assert "Created new AIMBAT project" in result.output

        # can't make a new project if one exists already
        result = runner.invoke(project.cli, ["new"])
        assert result.exit_code == 0
        assert (
            "Unable to create a new project: found existing project_file"
            in result.output
        )

        # TODO - info not implemented yet
        result = runner.invoke(project.cli, ["info"])
        assert result.exit_code == 1

        result = runner.invoke(project.cli, ["del", "--yes"])
        assert result.exit_code == 0
        assert not project_file.exists()

        result = runner.invoke(project.cli, ["del", "--yes"])
        assert result.exit_code == 0
        assert "Unable to delete project: project_file=" in result.output

        result = runner.invoke(project.cli, ["info"])
        assert result.exit_code == 0
        assert "Unable to show info: project_file=" in result.output
