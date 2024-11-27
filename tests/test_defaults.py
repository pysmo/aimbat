from aimbat.lib import defaults
from aimbat.app import app
from aimbat.lib.types import AimbatDefaultAttribute
from sqlmodel import Session
from typer.testing import CliRunner


class TestLibDefaults:
    def test_defaults(self, db_session: Session) -> None:
        assert defaults.get_default(db_session, AimbatDefaultAttribute.aimbat) is True

        defaults.set_default(db_session, AimbatDefaultAttribute.aimbat, False)
        assert defaults.get_default(db_session, AimbatDefaultAttribute.aimbat) is False

        defaults.reset_default(db_session, AimbatDefaultAttribute.aimbat)
        assert defaults.get_default(db_session, AimbatDefaultAttribute.aimbat) is True


class TestCliDefaults:
    def test_defaults(self, db_url) -> None:  # type: ignore
        """Test AIMBAT cli with defaults subcommand."""

        runner = CliRunner()
        result = runner.invoke(app, ["--db-url", db_url, "defaults"])
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "defaults", "list"])
        assert result.exit_code == 0
        for val in ["Name", "Value", "Description"]:
            assert val in result.output

        result = runner.invoke(
            app,
            [
                "--db-url",
                db_url,
                "defaults",
                "get",
                AimbatDefaultAttribute.initial_time_window_width,
            ],
        )
        assert result.exit_code == 0
        assert "15" in result.output

        result = runner.invoke(
            app,
            [
                "--db-url",
                db_url,
                "defaults",
                "set",
                AimbatDefaultAttribute.initial_time_window_width,
                "11",
            ],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            app,
            [
                "--db-url",
                db_url,
                "defaults",
                "get",
                AimbatDefaultAttribute.initial_time_window_width,
            ],
        )
        assert result.exit_code == 0
        assert "11" in result.output

        result = runner.invoke(
            app, ["--db-url", db_url, "defaults", "get", AimbatDefaultAttribute.aimbat]
        )
        assert result.exit_code == 0
        assert "True" in result.output

        # booleans are a bit more flexible...
        test_bool_true = ["True", "true", "yes", "Y"]
        test_bool_false = ["False", "no"]
        for i in test_bool_true:
            result = runner.invoke(
                app,
                [
                    "--db-url",
                    db_url,
                    "defaults",
                    "set",
                    AimbatDefaultAttribute.aimbat,
                    i,
                ],
            )
            assert result.exit_code == 0
            result = runner.invoke(
                app,
                ["--db-url", db_url, "defaults", "get", AimbatDefaultAttribute.aimbat],
            )
            assert result.exit_code == 0
            assert "True" in result.output
        for i in test_bool_false:
            result = runner.invoke(
                app,
                [
                    "--db-url",
                    db_url,
                    "defaults",
                    "set",
                    AimbatDefaultAttribute.aimbat,
                    i,
                ],
            )
            assert result.exit_code == 0
            result = runner.invoke(
                app,
                ["--db-url", db_url, "defaults", "get", AimbatDefaultAttribute.aimbat],
            )
            assert result.exit_code == 0
            assert "False" in result.output

        result = runner.invoke(
            app,
            ["--db-url", db_url, "defaults", "reset", AimbatDefaultAttribute.aimbat],
        )
        assert result.exit_code == 0

        result = runner.invoke(
            app, ["--db-url", db_url, "defaults", "get", AimbatDefaultAttribute.aimbat]
        )
        assert result.exit_code == 0
        assert "True" in result.output
