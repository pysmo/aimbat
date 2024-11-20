from click.testing import CliRunner
from importlib import reload


class TestLibUtils:
    def test_plotseis(self, sac_file_good, mock_show) -> None:  # type: ignore
        from aimbat.lib import project, data, utils

        _ = reload(project)

        project.project_new()

        data.data_add_files([sac_file_good], filetype="sac")
        utils.utils_plotseis(1)


class TestCliUtils:
    def test_sac_data(self, sac_file_good, mock_show) -> None:  # type: ignore
        """Test AIMBAT cli with utils subcommand."""

        from aimbat.lib import project, data, utils

        _ = reload(project)

        runner = CliRunner()

        result = runner.invoke(project.project_cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(data.data_cli, ["add"])
        assert result.exit_code == 2

        result = runner.invoke(data.data_cli, ["add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(utils.utils_cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(utils.utils_cli, ["plotseis", "1"])
        assert result.exit_code == 0
