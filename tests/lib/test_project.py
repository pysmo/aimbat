from click.testing import CliRunner
from pathlib import Path
import pytest


class TestProject:

    @pytest.mark.usefixtures("project_directory")
    def test_lib_project(self, project_directory) -> None:  # type: ignore

        from aimbat.lib import project as lib

        self.project_file = Path(f"{project_directory}/aimbat.db")

        # try deleting a project when there is none
        assert not self.project_file.exists()
        with pytest.raises(FileNotFoundError):
            lib.project_del(str(self.project_file))

        # try getting project info when there is no project
        with pytest.raises(FileNotFoundError):
            lib.project_info(str(self.project_file))

        # create project
        project_file_out = lib.project_new(str(self.project_file))
        assert self.project_file.exists()
        assert str(self.project_file) == project_file_out

        # try creating again
        with pytest.raises(FileExistsError):
            lib.project_new(str(self.project_file))

        # TODO: change this when info is implemented
        with pytest.raises(NotImplementedError):
            lib.project_info(str(self.project_file))

        # delete project
        lib.project_del(str(self.project_file))
        assert not self.project_file.exists()


@pytest.mark.depends(depends=["TestProject.test_lib_project",
                              "/tests/test_cli.py::test_cli"], scope="session")
def test_cli_project() -> None:
    """Test AIMBAT cli with project subcommand."""
    from aimbat.lib import project, db

    project_file = Path(db.AIMBAT_PROJECT)

    runner = CliRunner()
    result = runner.invoke(project.cli)
    assert result.exit_code == 0
    assert 'Usage' in result.output

    result = runner.invoke(project.cli, ['new'])
    assert result.exit_code == 0
    assert project_file.exists()
    assert "Created new AIMBAT project" in result.output

    # can't make a new project if one exists already
    result = runner.invoke(project.cli, ['new'])
    assert result.exit_code == 0
    assert "Unable to create a new project: found existing project_file" in result.output

    # TODO - info not implemented yet
    result = runner.invoke(project.cli, ['info'])
    assert result.exit_code == 1

    result = runner.invoke(project.cli, ['del', '--yes'])
    assert result.exit_code == 0
    assert not project_file.exists()

    result = runner.invoke(project.cli, ['del', '--yes'])
    assert result.exit_code == 0
    assert "Unable to delete project: project_file=" in result.output

    result = runner.invoke(project.cli, ['info'])
    assert result.exit_code == 0
    assert "Unable to show info: project_file=" in result.output
