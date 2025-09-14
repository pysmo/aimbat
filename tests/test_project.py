from aimbat.lib import project, data, event
from aimbat.lib.models import AimbatEvent
from aimbat.lib.typing import SeismogramFileType
from aimbat.app import app
from sqlmodel import Session
from sqlalchemy.engine import Engine
from pathlib import Path
import platform
import pytest
import re


class TestLibProject:
    def test_project(
        self,
        db_engine: Engine,
        test_data: list[Path],
        capsys: pytest.CaptureFixture,
    ) -> None:
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
    def test_project(self, db_url: str, capsys: pytest.CaptureFixture) -> None:
        """Test AIMBAT cli with project subcommand."""

        app(["project"])
        assert "Usage" in capsys.readouterr().out

        app(["project", "create", "--db-url", db_url])
        with pytest.raises(RuntimeError):
            app(["project", "create", "--db-url", db_url])

        app(["project", "info", "--db-url", db_url])
        assert "AIMBAT Project File:" in capsys.readouterr().out

        # HACK - this does run on windows, but not on
        # github actions for some reason.
        if platform.system() != "Windows":
            app(["project", "delete", "--db-url", db_url])

            with pytest.raises(RuntimeError):
                app(["project", "delete", "--db-url", db_url])

            with pytest.raises(RuntimeError):
                app(["project", "info", "--db-url", db_url])
