from click.testing import CliRunner


class TestCliSeismogram:
    def test_sac_data(self, sac_file_good) -> None:  # type: ignore
        """Test AIMBAT cli with seismogram subcommand."""

        from aimbat.cli import data, project, seismogram

        runner = CliRunner()

        result = runner.invoke(project.project_cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(data.data_cli, ["add"])
        assert result.exit_code == 2

        result = runner.invoke(data.data_cli, ["add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(seismogram.seismogram_cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(seismogram.seismogram_cli, ["list"])
        assert result.exit_code == 0
        assert "pytest-of" in result.output

        result = runner.invoke(
            seismogram.seismogram_cli, ["parameter", "get", "1", "select"]
        )
        assert result.exit_code == 0
        assert "True" in result.output

        result = runner.invoke(
            seismogram.seismogram_cli, ["parameter", "set", "1", "select", "False"]
        )
        assert result.exit_code == 0

        result = runner.invoke(
            seismogram.seismogram_cli, ["parameter", "get", "1", "select"]
        )
        assert result.exit_code == 0
        assert "False" in result.output

        result = runner.invoke(
            seismogram.seismogram_cli, ["parameter", "set", "1", "select", "yes"]
        )
        assert result.exit_code == 0

        result = runner.invoke(
            seismogram.seismogram_cli, ["parameter", "get", "1", "select"]
        )
        assert result.exit_code == 0
        assert "True" in result.output

        result = runner.invoke(
            seismogram.seismogram_cli,
            ["parameter", "set", "1", "t1", "2011-11-04 00:15:23.283"],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            seismogram.seismogram_cli, ["parameter", "get", "1", "t1"]
        )
        assert result.exit_code == 0
        assert "2011-11-04 00:15:23.283" in result.output

        result = runner.invoke(
            seismogram.seismogram_cli,
            ["parameter", "set", "1", "t2", "2011-11-04 00:15:29.283"],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            seismogram.seismogram_cli, ["parameter", "get", "1", "t2"]
        )
        assert result.exit_code == 0
        assert "2011-11-04 00:15:29.283" in result.output
