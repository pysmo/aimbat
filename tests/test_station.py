from typer.testing import CliRunner


class TestCliStation:
    def test_sac_data(self, sac_file_good, db_url) -> None:  # type: ignore
        """Test AIMBAT cli with station subcommand."""

        from aimbat.app import app

        runner = CliRunner()

        result = runner.invoke(app, ["station"])
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "data", "add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "station", "list"])
        assert result.exit_code == 0
        assert "113A - AR" in result.output
