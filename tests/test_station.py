from collections.abc import Generator
from typing import Any
import pytest


class TestCliStationBase:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(
        self, test_data_string: list[str], db_url: str
    ) -> Generator[None, Any, Any]:
        """Setup and teardown for each test method."""
        from aimbat.app import app

        app(["project", "create", "--db-url", db_url])

        args = ["data", "add", "--db-url", db_url]
        args.extend(test_data_string)
        app(args)
        yield


class TestCliStation(TestCliStationBase):
    def test_sac_data(self, db_url: str, capsys: pytest.CaptureFixture) -> None:
        """Test AIMBAT cli with station subcommand."""

        from aimbat.app import app

        app("snapshot")
        assert "Usage" in capsys.readouterr().out

        with pytest.raises(RuntimeError):
            app(["station", "list", "--db-url", db_url])

        app(["station", "list", "--all", "--db-url", db_url])
        assert "BAK - CI" in capsys.readouterr().out

        app(["event", "activate", "1", "--db-url", db_url])

        app(["station", "list", "--db-url", db_url])
        assert "BAK - CI" in capsys.readouterr().out
