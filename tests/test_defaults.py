from __future__ import annotations
from sqlmodel import Session
from typing import TYPE_CHECKING
import pytest

if TYPE_CHECKING:
    from pytest import CaptureFixture
    from sqlalchemy.engine import Engine
    from collections.abc import Generator
    from typing import Any
    from pathlib import Path


class TestLibDefaults:
    @pytest.fixture
    def session(
        self, test_db_with_project: tuple[Path, str, Engine, Session]
    ) -> Generator[Session, Any, Any]:
        session = test_db_with_project[3]
        yield session

    def test_get_instance(self, session: Session) -> None:
        from aimbat.lib.defaults import _get_instance, AimbatDefaults

        assert isinstance(_get_instance(session), AimbatDefaults) is True

    @pytest.mark.dependency(name="get_default")
    def test_get_default(self, session: Session) -> None:
        from aimbat.lib.defaults import get_default, ProjectDefault

        assert get_default(session, ProjectDefault.AIMBAT) is True

    @pytest.mark.dependency(name="set_default", depends=["get_default"])
    def test_set_default(self, session: Session) -> None:
        from aimbat.lib.defaults import get_default, set_default, ProjectDefault

        assert get_default(session, ProjectDefault.AIMBAT) is True

        set_default(session, ProjectDefault.AIMBAT, False)
        assert get_default(session, ProjectDefault.AIMBAT) is False

    @pytest.mark.dependency(depends=["get_default", "set_default"])
    def test_reset_defaults(self, session: Session) -> None:
        from aimbat.lib.defaults import (
            get_default,
            set_default,
            reset_default,
            ProjectDefault,
        )

        set_default(session, ProjectDefault.AIMBAT, False)
        assert get_default(session, ProjectDefault.AIMBAT) is False
        reset_default(session, ProjectDefault.AIMBAT)
        assert get_default(session, ProjectDefault.AIMBAT) is True

    def test_print_defaults_table(
        self, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.lib.defaults import print_defaults_table

        print_defaults_table(session)

        captured = capsys.readouterr()
        assert "AIMBAT is awesome" in captured.out


class TestCliDefaults:
    @pytest.fixture
    def db_url(
        self, test_db_with_project: tuple[Path, str, Engine, Session]
    ) -> Generator[str, Any, Any]:
        url = test_db_with_project[1]
        yield url

    def test_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["defaults"])
        assert "Usage" in capsys.readouterr().out

    @pytest.mark.dependency(name="cli_get_default")
    def test_get_default(self, db_url: str, capsys: CaptureFixture) -> None:
        from aimbat.app import app
        from aimbat.lib.defaults import ProjectDefault

        app(
            [
                "defaults",
                "get",
                ProjectDefault.AIMBAT,
                "--db-url",
                db_url,
            ],
        )
        assert "True" in capsys.readouterr().out

        app(
            [
                "defaults",
                "get",
                ProjectDefault.TIME_WINDOW_PADDING,
                "--db-url",
                db_url,
            ],
        )
        assert "20.0s" in capsys.readouterr().out

    @pytest.mark.dependency(name="cli_set_default", depends=["cli_get_default"])
    def test_set_default(self, db_url: str, capsys: CaptureFixture) -> None:
        from aimbat.app import app
        from aimbat.lib.defaults import ProjectDefault

        app(
            [
                "defaults",
                "get",
                ProjectDefault.AIMBAT,
                "--db-url",
                db_url,
            ],
        )
        assert "True" in capsys.readouterr().out

        app(
            [
                "defaults",
                "set",
                ProjectDefault.AIMBAT,
                "False",
                "--db-url",
                db_url,
            ],
        )
        app(
            [
                "defaults",
                "get",
                ProjectDefault.AIMBAT,
                "--db-url",
                db_url,
            ],
        )
        assert "False" in capsys.readouterr().out

    @pytest.mark.dependency(
        name="cli_set_default", depends=["cli_get_default", "cli_set_default"]
    )
    def test_reset_default(self, db_url: str, capsys: CaptureFixture) -> None:
        from aimbat.app import app
        from aimbat.lib.defaults import ProjectDefault

        app(
            [
                "defaults",
                "get",
                ProjectDefault.AIMBAT,
                "--db-url",
                db_url,
            ],
        )
        captured = capsys.readouterr()
        assert "True" in captured.out

        app(
            [
                "defaults",
                "set",
                ProjectDefault.AIMBAT,
                "False",
                "--db-url",
                db_url,
            ],
        )
        captured = capsys.readouterr()
        assert captured.out == ""
        app(
            [
                "defaults",
                "get",
                ProjectDefault.AIMBAT,
                "--db-url",
                db_url,
            ],
        )
        captured = capsys.readouterr()
        assert "False" in captured.out

        app(
            [
                "defaults",
                "reset",
                ProjectDefault.AIMBAT,
                "--db-url",
                db_url,
            ],
        )
        captured = capsys.readouterr()
        assert captured.out == ""

        app(
            [
                "defaults",
                "get",
                ProjectDefault.AIMBAT,
                "--db-url",
                db_url,
            ],
        )
        captured = capsys.readouterr()
        assert "True" in captured.out

    def test_list_defaults(self, db_url: str, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(
            [
                "defaults",
                "list",
                "--db-url",
                db_url,
            ],
        )
        captured = capsys.readouterr()
        assert "AIMBAT is awesome" in captured.out
