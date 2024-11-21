from click.testing import CliRunner


class TestCliDefaults:
    def test_defaults(self) -> None:
        """Test AIMBAT cli with defaults subcommand."""

        from aimbat.cli import project, defaults

        runner = CliRunner()
        result = runner.invoke(defaults.defaults_cli)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(project.project_cli, ["new"])
        assert result.exit_code == 0

        result = runner.invoke(defaults.defaults_cli, ["list"])
        assert result.exit_code == 0
        for val in ["Name", "Value", "Description"]:
            assert val in result.output

        result = runner.invoke(defaults.defaults_cli, ["list", "aimbat"])
        assert result.exit_code == 0
        assert "True" in result.output

        # booleans are a bit more flexible...
        test_bool_true = ["True", "yes", "1"]
        test_bool_false = ["False", "no", "0"]
        for i in test_bool_true:
            result = runner.invoke(defaults.defaults_cli, ["set", "aimbat", i])
            assert result.exit_code == 0
            result = runner.invoke(defaults.defaults_cli, ["list", "aimbat"])
            assert result.exit_code == 0
            assert "True" in result.output
        for i in test_bool_false:
            result = runner.invoke(defaults.defaults_cli, ["set", "aimbat", i])
            assert result.exit_code == 0
            result = runner.invoke(defaults.defaults_cli, ["list", "aimbat"])
            assert result.exit_code == 0
            assert "False" in result.output

        result = runner.invoke(defaults.defaults_cli, ["reset", "aimbat"])
        assert result.exit_code == 0

        result = runner.invoke(defaults.defaults_cli, ["list", "aimbat"])
        assert result.exit_code == 0
        assert "True" in result.output
