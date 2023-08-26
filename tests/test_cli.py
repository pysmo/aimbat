from click.testing import CliRunner
from aimbat import cli
from aimbat.commands import (
    project,
    defaults,
    sampledata
)
import pytest
import os
from pathlib import Path


class TestAimbatCLI:

    print(f"AIMBAT_PROJECT={os.getenv('AIMBAT_PROJECT')}")

    project_file = Path(str(os.getenv('AIMBAT_PROJECT')))

    def test_cli(self) -> None:
        """Test aimbat cli without any subcommands."""

        runner = CliRunner()

        result = runner.invoke(cli.cli)
        assert result.exit_code == 0
        assert 'Usage' in result.output

        result = runner.invoke(cli.cli, '--version')
        assert result.exit_code == 0
        assert 'aimbat, version' in result.output

    @pytest.mark.depends(depends=["tests/lib/test_project.py::TestProject.test_lib_project",
                                  "test_cli"], scope="session")
    def test_cli_project(self) -> None:
        """Test AIMBAT cli with project subcommand."""

        runner = CliRunner()
        result = runner.invoke(project.cli)
        assert result.exit_code == 0
        assert 'Usage' in result.output

        result = runner.invoke(project.cli, ['new'])
        assert result.exit_code == 0
        assert self.project_file.exists()

        # can't make a new project if one exists already
        result = runner.invoke(project.cli, ['new'])
        assert result.exit_code == 1

        # TODO - info not implemented yet
        result = runner.invoke(project.cli, ['info'])
        assert result.exit_code == 1

        result = runner.invoke(project.cli, ['del', '--yes'])
        assert result.exit_code == 0
        assert not self.project_file.exists()

        result = runner.invoke(project.cli, ['new'])
        assert result.exit_code == 0
        assert self.project_file.exists()

    @pytest.mark.depends(depends=["tests/lib/test_defaults.py::TestProject.test_lib_defaults",
                                  "test_cli_project"], scope="session")
    def test_cli_defaults(self) -> None:
        """Test AIMBAT cli with defaults subcommand."""

        runner = CliRunner()
        result = runner.invoke(defaults.cli)
        assert result.exit_code == 0
        assert 'Usage' in result.output

        result = runner.invoke(defaults.cli, ["list"])
        assert result.exit_code == 0
        for val in ["Name", "Value", "Description"]:
            assert val in result.output

        result = runner.invoke(defaults.cli, ["list", "aimbat"])
        assert result.exit_code == 0
        assert "True" in result.output

        result = runner.invoke(defaults.cli, ["set", "aimbat", "False"])
        assert result.exit_code == 0

        result = runner.invoke(defaults.cli, ["list", "aimbat"])
        assert result.exit_code == 0
        assert "False" in result.output

        result = runner.invoke(defaults.cli, ["reset", "aimbat"])
        assert result.exit_code == 0

        result = runner.invoke(defaults.cli, ["list", "aimbat"])
        assert result.exit_code == 0
        assert "True" in result.output

    @pytest.mark.depends(depends=["tests/lib/test_defaults.py::TestProject.test_lib_defaults",
                                  "test_cli_project"], scope="session")
    def test_cli_sampledata(self, project_directory) -> None:  # type: ignore
        """Test AIMBAT cli with defaults subcommand."""

        sampledata_dir = Path(f"{project_directory}/aimbat-test")

        runner = CliRunner()
        result = runner.invoke(sampledata.cli)
        assert result.exit_code == 0
        assert 'Usage' in result.output

        result = runner.invoke(defaults.cli, ["set", "sampledata_dir", str(sampledata_dir)])
        assert result.exit_code == 0

        assert not sampledata_dir.exists()
        result = runner.invoke(sampledata.cli, ["download"])
        assert result.exit_code == 0
        assert sampledata_dir.exists()

        # can't download if it is already there
        result = runner.invoke(sampledata.cli, ["download"])
        assert result.exit_code == 1

        # unless we use force
        result = runner.invoke(sampledata.cli, ["download", "-f"])
        assert result.exit_code == 0

        result = runner.invoke(sampledata.cli, ["delete"])
        assert result.exit_code == 0
        assert not sampledata_dir.exists()

        result = runner.invoke(defaults.cli, ["reset", "sampledata_dir"])
        assert result.exit_code == 0
