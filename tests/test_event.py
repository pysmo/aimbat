from aimbat.lib import data, event
from aimbat.lib.models import AimbatEvent
from aimbat.app import app
import pytest
from aimbat.lib.typing import SeismogramFileType


class TestLibEvent:
    def test_active_event(self, db_session, test_data) -> None:  # type: ignore
        data.add_files_to_project(
            db_session, test_data, filetype=SeismogramFileType.SAC
        )

        with pytest.raises(RuntimeError):
            event.get_active_event(db_session)
        aimbat_event = db_session.get(AimbatEvent, 1)
        assert aimbat_event.active is None
        event.set_active_event(db_session, aimbat_event)
        assert aimbat_event.active is not None
        assert event.get_active_event(db_session) is aimbat_event
        aimbat_event = db_session.get(AimbatEvent, 2)
        event.set_active_event(db_session, aimbat_event)
        assert event.get_active_event(db_session) is aimbat_event

    def test_station_link(self, db_session, test_data) -> None:  # type: ignore
        data.add_files_to_project(
            db_session, test_data, filetype=SeismogramFileType.SAC
        )

        aimbat_event = db_session.get(AimbatEvent, 1)
        assert aimbat_event.stations[0].id == 1


class TestCliEvent:
    def test_sac_data(self, db_url, test_data_string, capsys) -> None:  # type: ignore
        """Test AIMBAT cli with event subcommand."""

        app(["event"])
        assert "Usage" in capsys.readouterr().out

        app(["project", "create", "--db-url", db_url])

        args = ["data", "add", "--db-url", db_url]
        args.extend(test_data_string)
        app(args)

        app(["event", "list", "--db-url", db_url])
        assert "2011-09-15 19:31:04.080000" in capsys.readouterr().out

        with pytest.raises(ValueError):
            app(["event", "activate", "100000", "--db-url", db_url])

        app(["event", "activate", "1", "--db-url", db_url])
        app(["event", "list", "--db-url", db_url])
        assert "\u2714" in capsys.readouterr().out

        app(["event", "set", "--db-url", db_url, "window_pre", "--", "-2.3"])
        app(["event", "get", "window_pre", "--db-url", db_url])
        assert "-2.3" in capsys.readouterr().out

        app(["event", "set", "--db-url", db_url, "window_post", "--", "5.3"])
        app(["event", "get", "window_post", "--db-url", db_url])
        assert "5.3" in capsys.readouterr().out

        with pytest.raises(ValueError):
            app(
                [
                    "event",
                    "set",
                    "--db-url",
                    db_url,
                    "window_pre",
                    "--",
                    "cannot_convert_this_to_float",
                ]
            )

        app(
            [
                "event",
                "set",
                "--db-url",
                db_url,
                "completed",
                "--",
                "True",
            ]
        )
        app(
            [
                "event",
                "get",
                "--db-url",
                db_url,
                "completed",
            ]
        )
        assert "True" in capsys.readouterr().out

        app(["event", "set", "--db-url", db_url, "completed", "--", "False"])
        app(["event", "get", "--db-url", db_url, "completed"])
        assert "False" in capsys.readouterr().out
