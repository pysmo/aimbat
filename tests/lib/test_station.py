from click.testing import CliRunner
from importlib import reload


class TestCliStation:
    def test_sac_data(self, sac_file_good) -> None:  # type: ignore
        """Test AIMBAT cli with station subcommand."""

        from aimbat.lib import project, data, station

        reload(project)

        runner = CliRunner()

        result = runner.invoke(project.project_cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(station.station_cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(data.data_cli, ["add"])
        assert result.exit_code == 2

        result = runner.invoke(data.data_cli, ["add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(station.station_cli, ["list"])
        assert result.exit_code == 0
        assert "113A - AR" in result.output
