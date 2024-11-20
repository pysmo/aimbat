from click.testing import CliRunner

# import pytest
from pathlib import Path
from importlib import reload


class TestCliSampleData:
    def test_cli_sampledata(self, project_directory) -> None:  # type: ignore
        """Test AIMBAT cli with defaults subcommand."""

        from aimbat.lib import project, defaults, sampledata

        reload(project)
        reload(sampledata)

        sampledata_dir = Path(f"{project_directory}/aimbat-test")

        runner = CliRunner()
        result = runner.invoke(sampledata.sampledata_cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(project.project_cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(
            defaults.defaults_cli, ["set", "sampledata_dir", str(sampledata_dir)]
        )
        assert result.exit_code == 0

        assert not sampledata_dir.exists()
        result = runner.invoke(sampledata.sampledata_cli, ["download"])
        assert result.exit_code == 0
        assert sampledata_dir.exists()

        # can't download if it is already there
        result = runner.invoke(sampledata.sampledata_cli, ["download"])
        assert result.exit_code == 1

        # unless we use force
        result = runner.invoke(sampledata.sampledata_cli, ["download", "-f"])
        assert result.exit_code == 0

        result = runner.invoke(sampledata.sampledata_cli, ["delete"])
        assert result.exit_code == 0
        assert not sampledata_dir.exists()

        result = runner.invoke(defaults.defaults_cli, ["reset", "sampledata_dir"])
        assert result.exit_code == 0
