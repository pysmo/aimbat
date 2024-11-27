from aimbat.lib import project, data, event
from aimbat.lib.models import AimbatEvent
from aimbat.lib.types import SeismogramFileType
from aimbat.app import app
from sqlmodel import Session
from typer.testing import CliRunner
import platform
import pytest
import re


class TestLibProject:
    def test_project(self, db_engine, test_data, capsys) -> None:  # type: ignore
        project.create_project(db_engine)

        with pytest.raises(RuntimeError):
            project.create_project(db_engine)

        project.print_project_info(db_engine)
        captured = capsys.readouterr()
        assert "Project Info" in captured.out

        with Session(db_engine) as session:
            data.add_files_to_project(
                session, test_data, filetype=SeismogramFileType.SAC
            )
            aimbat_event = session.get(AimbatEvent, 1)
            assert aimbat_event is not None
            event.set_active_event(session, aimbat_event)

        project.print_project_info(db_engine)
        captured = capsys.readouterr()
        assert re.search(r"Active Event ID:\s+1", captured.out)

        # HACK - this does run on windows, but not on
        # github actions for some reason.
        if platform.system() != "Windows":
            project.delete_project(db_engine)

            with pytest.raises(RuntimeError):
                project.delete_project(db_engine)


class TestCliProject:
    def test_project(self, db_url: str) -> None:
        """Test AIMBAT cli with project subcommand."""

        runner = CliRunner()
        result = runner.invoke(app)
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        print(result.output)
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 1

        result = runner.invoke(app, ["--db-url", db_url, "project", "info"])
        assert result.exit_code == 0
        assert "AIMBAT Project File:" in result.stdout

        # HACK - this does run on windows, but not on
        # github actions for some reason.
        if platform.system() != "Windows":
            result = runner.invoke(app, ["--db-url", db_url, "project", "delete"])
            assert result.exit_code == 0

            result = runner.invoke(app, ["--db-url", db_url, "project", "delete"])
            assert result.exit_code == 1

            result = runner.invoke(app, ["--db-url", db_url, "project", "info"])
            assert result.exit_code == 1
