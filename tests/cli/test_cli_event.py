from click.testing import CliRunner
import re


class TestCliEvent:
    def test_sac_data(self, sac_file_good) -> None:  # type: ignore
        """Test AIMBAT cli with event subcommand."""

        from aimbat.cli import data, project, event

        runner = CliRunner()

        result = runner.invoke(project.project_cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(data.data_cli, ["add"])
        assert result.exit_code == 2

        result = runner.invoke(data.data_cli, ["add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(event.event_cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(event.event_cli, ["list"])
        assert result.exit_code == 0
        assert "2011-09-15 19:31:04.080000" in result.output

        result = runner.invoke(event.event_cli, ["select", "1"])
        assert result.exit_code == 0
        result = runner.invoke(event.event_cli, ["list"])
        assert re.search(r".*1\s+\│\s+True\s+\│\s+2011-09-15.*", result.output)

        result = runner.invoke(
            event.event_cli, ["parameter", "set", "1", "window_pre", "--", "-2.3"]
        )
        assert result.exit_code == 0

        result = runner.invoke(event.event_cli, ["parameter", "get", "1", "window_pre"])
        assert result.exit_code == 0
        assert "-1 day, 23:59:57.7" in result.output

        result = runner.invoke(
            event.event_cli, ["parameter", "set", "1", "window_post", "--", "5.3"]
        )
        assert result.exit_code == 0

        result = runner.invoke(
            event.event_cli, ["parameter", "get", "1", "window_post"]
        )
        assert result.exit_code == 0
        assert "0:00:05.3" in result.output

        result = runner.invoke(
            event.event_cli,
            [
                "parameter",
                "set",
                "1",
                "window_pre",
                "--",
                "cannot_convert_this_to_float",
            ],
        )
        assert result.exit_code == 1
        assert result.exception
