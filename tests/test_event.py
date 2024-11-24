from sqlmodel import select
from aimbat.lib.models import AimbatEvent
from typer.testing import CliRunner
import re
import pytest


class TestLibEvent:
    def test_active_event(self, db_session, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import data, event

        data.add_files_to_project(db_session, [sac_file_good], filetype="sac")

        with pytest.raises(RuntimeError):
            event.get_active_event(db_session)
        select_aimbat_event = select(AimbatEvent).where(AimbatEvent.id == 1)
        aimbat_event = db_session.exec(select_aimbat_event).one()
        assert aimbat_event.is_active is False
        event.set_active_event(db_session, aimbat_event)
        assert aimbat_event.is_active is True
        assert event.get_active_event(db_session) is aimbat_event

    def test_station_link(self, db_session, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import data

        data.add_files_to_project(db_session, [sac_file_good], filetype="sac")

        select_event = select(AimbatEvent).where(AimbatEvent.id == 1)
        aimbat_event = db_session.exec(select_event).one()
        assert aimbat_event.stations[0].id == 1


class TestCliEvent:
    def test_sac_data(self, db_url, sac_file_good) -> None:  # type: ignore
        """Test AIMBAT cli with event subcommand."""

        from aimbat.app import app

        runner = CliRunner()

        result = runner.invoke(app, ["event"])
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "data", "add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "event", "list"])
        assert result.exit_code == 0
        assert "2011-09-15 19:31:04.080000" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "event", "activate", "100000"])
        assert result.exit_code == 1

        result = runner.invoke(app, ["--db-url", db_url, "event", "activate", "1"])
        assert result.exit_code == 0
        result = runner.invoke(app, ["--db-url", db_url, "event", "list"])
        assert re.search(r".*1\s+\│\s+True\s+\│\s+2011-09-15.*", result.output)

        result = runner.invoke(
            app, ["--db-url", db_url, "event", "set", "window_pre", "--", "-2.3"]
        )
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "event", "get", "window_pre"])
        assert result.exit_code == 0
        assert "-1 day, 23:59:57.7" in result.output

        result = runner.invoke(
            app, ["--db-url", db_url, "event", "set", "window_post", "--", "5.3"]
        )
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "event", "get", "window_post"])
        assert result.exit_code == 0
        assert "0:00:05.3" in result.output

        result = runner.invoke(
            app,
            [
                "--db-url",
                db_url,
                "event",
                "set",
                "window_pre",
                "--",
                "cannot_convert_this_to_float",
            ],
        )
        assert result.exit_code == 1
        assert result.exception

        result = runner.invoke(
            app, ["--db-url", db_url, "event", "set", "completed", "--", "True"]
        )
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "event", "get", "completed"])
        assert result.exit_code == 0
        assert "True" in result.output

        result = runner.invoke(
            app, ["--db-url", db_url, "event", "set", "completed", "--", "False"]
        )
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "event", "get", "completed"])
        assert result.exit_code == 0
        assert "False" in result.output
