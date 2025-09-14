from aimbat.app import app
from aimbat.lib import data, event
from aimbat.lib.models import AimbatEvent
from aimbat.lib.typing import SeismogramFileType
from sqlmodel import Session
from pathlib import Path
import pytest


class TestLibEventBase:
    @pytest.fixture(autouse=True)
    def setup(self, db_session_with_project: Session, test_data: list[Path]) -> None:
        data.add_files_to_project(
            db_session_with_project, test_data, filetype=SeismogramFileType.SAC
        )


class TestLibEvent(TestLibEventBase):
    def test_active_event(self, db_session_with_project: Session) -> None:
        with pytest.raises(RuntimeError):
            event.get_active_event(db_session_with_project)
        aimbat_event = db_session_with_project.get(AimbatEvent, 1)
        assert aimbat_event is not None
        assert aimbat_event.active is None
        event.set_active_event(db_session_with_project, aimbat_event)
        assert aimbat_event.active is not None
        assert event.get_active_event(db_session_with_project) is aimbat_event
        aimbat_event = db_session_with_project.get(AimbatEvent, 2)
        assert aimbat_event is not None
        event.set_active_event(db_session_with_project, aimbat_event)
        assert event.get_active_event(db_session_with_project) is aimbat_event

    def test_station_link(self, db_session_with_project: Session) -> None:
        aimbat_event = db_session_with_project.get(AimbatEvent, 1)
        assert aimbat_event is not None
        assert aimbat_event.stations[0].id == 1


class TestCliEvent:
    def test_usage(self, capsys: pytest.CaptureFixture) -> None:
        app(["event"])
        assert "Usage" in capsys.readouterr().out

    def test_sac_data(
        self, db_url_with_data: str, capsys: pytest.CaptureFixture
    ) -> None:
        """Test AIMBAT cli with event subcommand."""

        app(["event", "list", "--db-url", db_url_with_data])
        assert "2011-09-15 19:31:04.080000" in capsys.readouterr().out

        with pytest.raises(ValueError):
            app(["event", "activate", "100000", "--db-url", db_url_with_data])

        app(["event", "activate", "1", "--db-url", db_url_with_data])
        app(["event", "list", "--db-url", db_url_with_data])
        assert "\u2714" in capsys.readouterr().out

        app(["event", "set", "--db-url", db_url_with_data, "window_pre", "--", "-2.3"])
        app(["event", "get", "window_pre", "--db-url", db_url_with_data])
        assert "-2.3" in capsys.readouterr().out

        app(["event", "set", "--db-url", db_url_with_data, "window_post", "--", "5.3"])
        app(["event", "get", "window_post", "--db-url", db_url_with_data])
        assert "5.3" in capsys.readouterr().out

        with pytest.raises(ValueError):
            app(
                [
                    "event",
                    "set",
                    "--db-url",
                    db_url_with_data,
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
                db_url_with_data,
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
                db_url_with_data,
                "completed",
            ]
        )
        assert "True" in capsys.readouterr().out

        app(["event", "set", "--db-url", db_url_with_data, "completed", "--", "False"])
        app(["event", "get", "--db-url", db_url_with_data, "completed"])
        assert "False" in capsys.readouterr().out
