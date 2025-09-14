from aimbat.lib import defaults
from aimbat.app import app
from aimbat.lib.typing import ProjectDefault
from sqlmodel import Session
from collections.abc import Generator
from typing import Any
import pytest


class TestLibDefaults:
    def test_change_defaults(self, db_session: Session) -> None:
        assert defaults.get_default(db_session, ProjectDefault.AIMBAT) is True

        defaults.set_default(db_session, ProjectDefault.AIMBAT, False)
        assert defaults.get_default(db_session, ProjectDefault.AIMBAT) is False

        defaults.reset_default(db_session, ProjectDefault.AIMBAT)
        assert defaults.get_default(db_session, ProjectDefault.AIMBAT) is True


class TestCliDefaultsBase:
    @pytest.fixture(autouse=True)
    def setup(self, db_url: str) -> Generator[None, Any, Any]:
        app(["project", "create", "--db-url", db_url])
        try:
            yield
        finally:
            app(["project", "delete", "--db-url", db_url])


class TestCliDefaults(TestCliDefaultsBase):
    def test_defaults(self, db_url: str, capsys: pytest.CaptureFixture) -> None:
        """Test AIMBAT cli with defaults subcommand."""

        app(["defaults"])
        assert "Usage" in capsys.readouterr().out

        app(["defaults", "list", "--db-url", db_url])
        assert "Description" in capsys.readouterr().out

        app(
            [
                "defaults",
                "get",
                ProjectDefault.DELTA_TOLERANCE,
                "--db-url",
                db_url,
            ],
        )
        assert "9" in capsys.readouterr().out

        app(
            [
                "defaults",
                "set",
                ProjectDefault.DELTA_TOLERANCE,
                "10",
                "--db-url",
                db_url,
            ],
        )

        app(
            [
                "defaults",
                "get",
                ProjectDefault.INITIAL_TIME_WINDOW_WIDTH,
                "--db-url",
                db_url,
            ],
        )
        assert "30" in capsys.readouterr().out

        app(
            [
                "defaults",
                "set",
                ProjectDefault.INITIAL_TIME_WINDOW_WIDTH,
                "11",
                "--db-url",
                db_url,
            ],
        )

        app(
            [
                "defaults",
                "get",
                ProjectDefault.INITIAL_TIME_WINDOW_WIDTH,
                "--db-url",
                db_url,
            ],
        )
        assert "11" in capsys.readouterr().out

        app(["defaults", "get", ProjectDefault.AIMBAT, "--db-url", db_url])
        assert "True" in capsys.readouterr().out

        # booleans are a bit more flexible...
        test_bool_true = ["True", "true", "yes", "Y"]
        test_bool_false = ["False", "no"]
        for i in test_bool_true:
            app(
                [
                    "defaults",
                    "set",
                    ProjectDefault.AIMBAT,
                    i,
                    "--db-url",
                    db_url,
                ],
            )

            app(
                ["defaults", "get", ProjectDefault.AIMBAT, "--db-url", db_url],
            )
            assert "True" in capsys.readouterr().out
        for i in test_bool_false:
            app(
                [
                    "defaults",
                    "set",
                    ProjectDefault.AIMBAT,
                    i,
                    "--db-url",
                    db_url,
                ],
            )
            app(
                ["defaults", "get", ProjectDefault.AIMBAT, "--db-url", db_url],
            )
            assert "False" in capsys.readouterr().out

        app(
            [
                "defaults",
                "reset",
                ProjectDefault.AIMBAT,
                "--db-url",
                db_url,
            ],
        )
        app(["defaults", "get", ProjectDefault.AIMBAT, "--db-url", db_url])
        assert "True" in capsys.readouterr().out
