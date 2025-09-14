from aimbat.lib import data, seismogram
from aimbat.lib.typing import SeismogramFileType, SeismogramParameter
from aimbat.app import app
import pytest


class TestLibSeismogram:
    def test_get_parameter(self, db_session, test_data) -> None:  # type: ignore
        data.add_files_to_project(
            db_session, test_data, filetype=SeismogramFileType.SAC
        )

        assert (
            seismogram.get_seismogram_parameter_by_id(
                session=db_session,
                seismogram_id=1,
                parameter_name=SeismogramParameter.SELECT,
            )
            is True
        )
        assert (
            seismogram.get_seismogram_parameter_by_id(
                session=db_session,
                seismogram_id=1,
                parameter_name=SeismogramParameter.T1,
            )
            is None
        )
        with pytest.raises(ValueError):
            seismogram.get_seismogram_parameter_by_id(
                session=db_session,
                seismogram_id=1000,
                parameter_name=SeismogramParameter.SELECT,
            )

    def test_set_parameter(self, db_session, test_data) -> None:  # type: ignore
        data.add_files_to_project(
            db_session, test_data, filetype=SeismogramFileType.SAC
        )

        seismogram.set_seismogram_parameter_by_id(
            session=db_session,
            seismogram_id=1,
            parameter_name=SeismogramParameter.SELECT,
            parameter_value=False,
        )
        assert (
            seismogram.get_seismogram_parameter_by_id(
                session=db_session,
                seismogram_id=1,
                parameter_name=SeismogramParameter.SELECT,
            )
            is False
        )
        with pytest.raises(ValueError):
            seismogram.set_seismogram_parameter_by_id(
                session=db_session,
                seismogram_id=1000,  # this id doesn't exist
                parameter_name=SeismogramParameter.SELECT,
                parameter_value=False,
            )

    def test_plotseis(self, test_data, db_session, mock_show) -> None:  # type: ignore
        from aimbat.lib import data, event
        from aimbat.lib.models import AimbatEvent

        data.add_files_to_project(
            db_session, test_data, filetype=SeismogramFileType.SAC
        )

        aimbat_event = db_session.get(AimbatEvent, 1)
        assert aimbat_event.active is None
        event.set_active_event(db_session, aimbat_event)
        seismogram.plot_seismograms(db_session)


class TestCliSeismogram:
    def test_sac_data(self, db_url, test_data_string, monkeypatch, capsys) -> None:  # type: ignore
        """Test AIMBAT cli with seismogram subcommand."""

        monkeypatch.setenv("COLUMNS", "1000")

        app("seismogram")
        assert "Usage" in capsys.readouterr().out

        app(["project", "create", "--db-url", db_url])

        args = ["data", "add", "--db-url", db_url]
        args.extend(test_data_string)
        app(args)

        app(
            ["seismogram", "get", "1", SeismogramParameter.SELECT, "--db-url", db_url],
        )
        assert "True" in capsys.readouterr().out

        app(
            [
                "seismogram",
                "set",
                "1",
                SeismogramParameter.SELECT,
                "False",
                "--db-url",
                db_url,
            ]
        )

        app(["seismogram", "get", "1", SeismogramParameter.SELECT, "--db-url", db_url])
        assert "False" in capsys.readouterr().out

        app(
            [
                "seismogram",
                "set",
                "1",
                SeismogramParameter.SELECT,
                "yes",
                "--db-url",
                db_url,
            ]
        )

        with pytest.raises(ValueError):
            app(
                [
                    "seismogram",
                    "set",
                    "1",
                    SeismogramParameter.SELECT,
                    "noooooooooooooo",
                    "--db-url",
                    db_url,
                ],
            )

        app(["seismogram", "get", "1", SeismogramParameter.SELECT, "--db-url", db_url])
        assert "True" in capsys.readouterr().out

        app(
            [
                "seismogram",
                "set",
                "1",
                "t1",
                "2011-11-04 00:15:23.283",
                "--db-url",
                db_url,
            ]
        )

        app(["seismogram", "get", "1", SeismogramParameter.T1, "--db-url", db_url])
        assert "2011-11-04 00:15:23.283" in capsys.readouterr().out

        with pytest.raises(RuntimeError):
            app(["seismogram", "list", "--db-url", db_url])

        app(["seismogram", "list", "--all", "--db-url", db_url])
        assert test_data_string[0] in capsys.readouterr().out

        app(["event", "activate", "1", "--db-url", db_url])
        app(["seismogram", "list", "--db-url", db_url])

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

        app(["seismogram", "plot", "--db-url", db_url])

        # app(["seismogram", "plot", "--db-url", db_url, "--use-qt"])
