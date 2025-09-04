from aimbat.lib.models import AimbatEvent
from aimbat.lib.typing import SeismogramFileType


class TestLibUtils:
    def test_plotseis(self, test_data, db_session, mock_show) -> None:  # type: ignore
        from aimbat.lib import data, plot, event

        data.add_files_to_project(
            db_session, test_data, filetype=SeismogramFileType.SAC
        )

        aimbat_event = db_session.get(AimbatEvent, 1)
        assert aimbat_event.active is None
        event.set_active_event(db_session, aimbat_event)
        plot.plot_seismograms(db_session)


class TestCliUtils:
    def test_plotseis(self, test_data_string, db_url, mock_show, capsys) -> None:  # type: ignore
        """Test AIMBAT cli with utils subcommand."""

        from aimbat.app import app

        app(["utils"])
        assert "Usage" in capsys.readouterr().out

        app(["project", "create", "--db-url", db_url])

        args = ["data", "add", "--db-url", db_url]
        args.extend(test_data_string)
        app(args)

        app(["event", "activate", "1", "--db-url", db_url])

        app(["plot", "seismograms", "--db-url", db_url])

        # app(["plot", "seismograms", "--db-url", db_url, "--use-qt"])
