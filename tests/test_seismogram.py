from aimbat.lib import data, seismogram
from aimbat.lib.typing import SeismogramFileType, SeismogramParameter
from aimbat.app import app
from collections.abc import Generator
from typing import Any
from pathlib import Path
from sqlmodel import Session
import pytest


class TestLibSeismogramBase:
    @pytest.fixture(autouse=True)
    def setup(self, db_session_with_project: Session, test_data: list[Path]) -> None:
        data.add_files_to_project(
            db_session_with_project, test_data, filetype=SeismogramFileType.SAC
        )


class TestLibSeismogramParameter(TestLibSeismogramBase):
    def test_get_parameter(self, db_session_with_project: Session) -> None:
        assert (
            seismogram.get_seismogram_parameter_by_id(
                session=db_session_with_project,
                seismogram_id=1,
                parameter_name=SeismogramParameter.SELECT,
            )
            is True
        )
        assert (
            seismogram.get_seismogram_parameter_by_id(
                session=db_session_with_project,
                seismogram_id=1,
                parameter_name=SeismogramParameter.T1,
            )
            is None
        )
        with pytest.raises(ValueError):
            seismogram.get_seismogram_parameter_by_id(
                session=db_session_with_project,
                seismogram_id=1000,
                parameter_name=SeismogramParameter.SELECT,
            )

    def test_set_parameter(self, db_session_with_project: Session) -> None:
        seismogram.set_seismogram_parameter_by_id(
            session=db_session_with_project,
            seismogram_id=1,
            parameter_name=SeismogramParameter.SELECT,
            parameter_value=False,
        )
        assert (
            seismogram.get_seismogram_parameter_by_id(
                session=db_session_with_project,
                seismogram_id=1,
                parameter_name=SeismogramParameter.SELECT,
            )
            is False
        )
        with pytest.raises(ValueError):
            seismogram.set_seismogram_parameter_by_id(
                session=db_session_with_project,
                seismogram_id=1000,  # this id doesn't exist
                parameter_name=SeismogramParameter.SELECT,
                parameter_value=False,
            )


class TestLibSeismogramPlot(TestLibSeismogramBase):
    def test_plotseis(
        self, db_session_with_project: Session, mock_show: pytest.FixtureDef
    ) -> None:
        from aimbat.lib import event
        from aimbat.lib.models import AimbatEvent

        aimbat_event = db_session_with_project.get(AimbatEvent, 1)
        assert aimbat_event is not None
        assert aimbat_event.active is None
        event.set_active_event(db_session_with_project, aimbat_event)
        seismogram.plot_seismograms(db_session_with_project)


class TestCliSeismogramBase:
    @pytest.fixture(autouse=True)
    def setup(
        self, db_url: str, test_data_string: list[str]
    ) -> Generator[None, Any, Any]:
        app(["project", "create", "--db-url", db_url])
        args = ["data", "add", "--db-url", db_url]
        args.extend(test_data_string)
        app(args)
        yield

    def test_usage(self, capsys: pytest.CaptureFixture) -> None:
        app("seismogram")
        assert "Usage" in capsys.readouterr().out


class TestCliSeismogramParameter(TestCliSeismogramBase):
    def test_get_parameter(
        self,
        db_url: str,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        monkeypatch.setenv("COLUMNS", "1000")

        app(
            ["seismogram", "get", "1", SeismogramParameter.SELECT, "--db-url", db_url],
        )
        assert "True" in capsys.readouterr().out

    def test_set_parameter(
        self,
        db_url: str,
        test_data_string: list[str],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        monkeypatch.setenv("COLUMNS", "1000")

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
        app(["seismogram", "get", "1", SeismogramParameter.SELECT, "--db-url", db_url])
        assert "True" in capsys.readouterr().out

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


class TestCliSeismogramPlot(TestCliSeismogramBase):
    def test_plotseis(self, db_url: str, mock_show: pytest.FixtureDef) -> None:
        """Test AIMBAT cli with utils subcommand."""

        app(["event", "activate", "1", "--db-url", db_url])

        app(["seismogram", "plot", "--db-url", db_url])

        # app(["seismogram", "plot", "--db-url", db_url, "--use-qt"])
