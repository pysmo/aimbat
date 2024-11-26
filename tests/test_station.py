from typer.testing import CliRunner


class TestCliStation:
    def test_sac_data(self, test_data_string, db_url) -> None:  # type: ignore
        """Test AIMBAT cli with station subcommand."""

        from aimbat.app import app

        runner = CliRunner()

        result = runner.invoke(app, ["station"])
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 0

        args = ["--db-url", db_url, "data", "add"]
        args.extend(test_data_string)
        result = runner.invoke(app, args)
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "station", "list"])
        assert result.exit_code == 1

        result = runner.invoke(app, ["--db-url", db_url, "station", "list", "--all"])
        assert result.exit_code == 0
        assert "BAK - CI" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "event", "activate", "1"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "station", "list"])
        assert result.exit_code == 0
