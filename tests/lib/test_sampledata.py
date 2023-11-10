from click.testing import CliRunner
import pytest
from pathlib import Path
from importlib import reload


@pytest.mark.usefixtures("mock_project_env")
class TestSampleData:
    @pytest.mark.depends(
        depends=["tests/lib/test_defaults.py::test_cli_defaults", "test_cli_project"],
        scope="session",
    )
    def test_cli_sampledata(self, project_directory) -> None:  # type: ignore
        """Test AIMBAT cli with defaults subcommand."""

        from aimbat.lib import sampledata, defaults, project, db

        reload(db)
        reload(defaults)
        reload(project)
        reload(sampledata)

        sampledata_dir = Path(f"{project_directory}/aimbat-test")

        runner = CliRunner()
        result = runner.invoke(sampledata.cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(project.cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(
            defaults.cli, ["set", "sampledata_dir", str(sampledata_dir)]
        )
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
