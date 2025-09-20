from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING
import platform
import pytest

if TYPE_CHECKING:
    from pytest import CaptureFixture
    from sqlmodel import Session
    from sqlalchemy.engine import Engine
    from collections.abc import Generator
    from typing import Any


class TestLibProject:
    @pytest.fixture
    def engine(
        self, test_db: tuple[Path, str, Engine, Session]
    ) -> Generator[Engine, Any, Any]:
        yield test_db[2]

    @pytest.fixture
    def engine_with_active_event(
        self, test_db_with_active_event: tuple[Path, str, Engine, Session]
    ) -> Generator[Engine, Any, Any]:
        yield test_db_with_active_event[2]

    @pytest.fixture
    def path(
        self, test_db: tuple[Path, str, Engine, Session]
    ) -> Generator[Path, Any, Any]:
        yield test_db[0]

    def test_no_project_exits(self, engine: Engine) -> None:
        from aimbat.lib.project import _project_exists

        assert _project_exists(engine=engine) is False

    def test_project_file_from_engine(self, engine: Engine, path: Path) -> None:
        from aimbat.lib.project import _project_file_from_engine

        assert _project_file_from_engine(engine=engine) == path

    @pytest.mark.dependency(name="create_project")
    def test_create_project(self, engine: Engine) -> None:
        from aimbat.lib.project import create_project

        create_project(engine)

        with pytest.raises(RuntimeError):
            create_project(engine)

    @pytest.mark.dependency(name="project_exists", depends=["create_project"])
    def test_project_exists(self, engine: Engine) -> None:
        from aimbat.lib.project import _project_exists, create_project

        create_project(engine)

        assert _project_exists(engine=engine) is True

    @pytest.mark.skipif(
        platform.system() == "Windows", reason="Doesn't run on github actions"
    )
    @pytest.mark.dependency(name="delete_project", depends=["create_project"])
    def test_delete_project(self, engine: Engine) -> None:
        from aimbat.lib.project import create_project, delete_project

        create_project(engine)
        delete_project(engine)
        with pytest.raises(RuntimeError):
            delete_project(engine)

    def test_print_project_info_with_no_project(self, engine: Engine) -> None:
        from aimbat.lib.project import print_project_info

        with pytest.raises(RuntimeError):
            print_project_info(engine)

    @pytest.mark.dependency(name="project_info", depends=["create_project"])
    def test_print_project_info(self, engine: Engine, capsys: CaptureFixture) -> None:
        from aimbat.lib.project import create_project, print_project_info

        create_project(engine)
        print_project_info(engine)
        captured = capsys.readouterr()
        assert "Project Info" in captured.out
        assert "None" in captured.out

    @pytest.mark.dependency(depends=["project_info"])
    def test_print_project_info_with_active_event(
        self, engine_with_active_event: Engine, capsys: CaptureFixture
    ) -> None:
        from aimbat.lib.project import print_project_info

        print_project_info(engine_with_active_event)
        captured = capsys.readouterr()
        assert "(3/0)" in captured.out


class TestCliProject:
    @pytest.fixture
    def engine(
        self, test_db: tuple[Path, str, Engine, Session]
    ) -> Generator[Engine, Any, Any]:
        yield test_db[2]

    @pytest.fixture
    def db_url(
        self, test_db: tuple[Path, str, Engine, Session]
    ) -> Generator[str, Any, Any]:
        yield test_db[1]

    def test_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["project"])
        assert "Usage" in capsys.readouterr().out

    @pytest.mark.dependency(depends=["project_exists"])
    def test_project_create(self, engine: Engine, db_url: str) -> None:
        """Test AIMBAT cli with project subcommand."""
        from aimbat.app import app
        from aimbat.lib.project import _project_exists

        app(["project", "create", "--db-url", db_url])
        with pytest.raises(RuntimeError):
            app(["project", "create", "--db-url", db_url])

        assert _project_exists(engine=engine) is True

    @pytest.mark.skipif(
        platform.system() == "Windows", reason="Doesn't run on github actions"
    )
    @pytest.mark.dependency(depends=["create_project"])
    def test_project_delete(self, engine: Engine, db_url: str) -> None:
        """Test AIMBAT cli with project subcommand."""
        from aimbat.lib.project import create_project
        from aimbat.app import app

        create_project(engine)

        app(["project", "delete", "--db-url", db_url])
        with pytest.raises(RuntimeError):
            app(["project", "delete", "--db-url", db_url])

    @pytest.mark.dependency(depends=["create_project"])
    def test_project_info(
        self, engine: Engine, db_url: str, capsys: CaptureFixture
    ) -> None:
        """Test AIMBAT cli with project subcommand."""
        from aimbat.lib.project import create_project
        from aimbat.app import app

        create_project(engine)

        app(["project", "info", "--db-url", db_url])
        assert "AIMBAT Project File:" in capsys.readouterr().out
