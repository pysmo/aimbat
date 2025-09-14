from aimbat.app import app
from aimbat.lib import data, snapshot, event
from aimbat.lib.models import AimbatSnapshot, AimbatEvent
from aimbat.lib.typing import SeismogramFileType
from sqlmodel import select, Session
from collections.abc import Generator
from typing import Any
from pathlib import Path
import pytest
import uuid


RANDOM_COMMENT = str(uuid.uuid4())[:5]


class TestLibSnapshotBase:
    select_event = select(AimbatEvent).where(AimbatEvent.id == 1)
    select_snapshots = select(AimbatSnapshot)

    @pytest.fixture(autouse=True)
    def setup(self, db_session: Session, test_data: list[Path]) -> None:
        data.add_files_to_project(
            db_session, test_data, filetype=SeismogramFileType.SAC
        )


class TestLibSnapshotCreate(TestLibSnapshotBase):
    def test_create(self, db_session: Session) -> None:
        with pytest.raises(RuntimeError):
            snapshot.create_snapshot(db_session)

        active_event = db_session.exec(self.select_event).one()
        event.set_active_event(db_session, active_event)
        assert event.get_active_event(db_session).id == 1

        assert snapshot.get_snapshots(db_session) == []
        snapshot.create_snapshot(db_session)
        snapshot.create_snapshot(db_session, comment=RANDOM_COMMENT)
        test_snapshot1, test_snapshot2, *_ = snapshot.get_snapshots(db_session)
        assert test_snapshot1.id == 1
        assert test_snapshot2.id == 2
        assert test_snapshot1.comment is None
        assert test_snapshot2.comment == RANDOM_COMMENT


class TestLibSnapshotDelete(TestLibSnapshotCreate):
    def test_delete(self, db_session: Session) -> None:
        snapshot.delete_snapshot_by_id(db_session, 1)
        assert len(db_session.exec(self.select_snapshots).all()) == 1
        test_snapshot = db_session.exec(self.select_snapshots).one()
        assert test_snapshot.id == 2
        with pytest.raises(ValueError):
            snapshot.delete_snapshot_by_id(db_session, 1)


class TestLibSnapshotRollback(TestLibSnapshotCreate):
    def test_rollback(self, db_session: Session) -> None:
        active_event = db_session.exec(self.select_event).one()
        assert active_event.parameters.completed is False

        active_event.parameters.completed = True
        db_session.add(active_event)
        db_session.commit()
        assert active_event.parameters.completed is True
        test_snapshot, *_ = snapshot.get_snapshots(db_session)
        snapshot.rollback_to_snapshot(db_session, test_snapshot)
        assert active_event.parameters.completed is False


class TestCliSnapshotBase:
    @pytest.fixture(autouse=True)
    def setup(self, db_url: str, test_data_string: str) -> Generator[None, Any, Any]:
        app(["project", "create", "--db-url", db_url])
        args = ["data", "add", "--db-url", db_url]
        args.extend(test_data_string)
        app(args)
        try:
            yield
        finally:
            app(["project", "delete", "--db-url", db_url])


class TestCliSnapshotUsage(TestCliSnapshotBase):
    def test_usage(self, capsys: pytest.CaptureFixture) -> None:
        app("snapshot")
        assert "Usage" in capsys.readouterr().out


class TestCliSnapshotCreate(TestCliSnapshotBase):
    def test_with_no_active_event(self, db_url: str) -> None:
        with pytest.raises(RuntimeError):
            app(["snapshot", "create", "--db-url", db_url])

        with pytest.raises(RuntimeError):
            app(["snapshot", "list", "--db-url", db_url])

    def test_with_active_event(
        self, db_url: str, capsys: pytest.CaptureFixture
    ) -> None:
        app(["event", "activate", "1", "--db-url", db_url])

        app(["event", "get", "completed", "--db-url", db_url])
        assert "False" in capsys.readouterr().out

        app(["snapshot", "create", "--db-url", db_url])
        app(["event", "set", "completed", "True", "--db-url", db_url])
        app(["event", "get", "completed", "--db-url", db_url])
        assert "True" in capsys.readouterr().out

    def test_with_comment(self, db_url: str, capsys: pytest.CaptureFixture) -> None:
        app(["event", "activate", "1", "--db-url", db_url])
        app(["snapshot", "create", "--comment", RANDOM_COMMENT, "--db-url", db_url])
        app(["snapshot", "list", "--db-url", db_url])
        assert RANDOM_COMMENT in capsys.readouterr().out


class TestCliSnapshotDelete(TestCliSnapshotBase):
    def test_with_comment(self, db_url: str, capsys: pytest.CaptureFixture) -> None:
        app(["event", "activate", "1", "--db-url", db_url])
        app(["snapshot", "create", "--comment", RANDOM_COMMENT, "--db-url", db_url])
        app(["snapshot", "list", "--db-url", db_url])
        assert RANDOM_COMMENT in capsys.readouterr().out
        app(["snapshot", "delete", "1", "--db-url", db_url])
        assert RANDOM_COMMENT not in capsys.readouterr().out


class TestCliSnapshotRollback(TestCliSnapshotBase):
    def test_rollback(self, db_url: str, capsys: pytest.CaptureFixture) -> None:
        app(["event", "activate", "1", "--db-url", db_url])
        app(["event", "get", "completed", "--db-url", db_url])
        assert "False" in capsys.readouterr().out
        app(["snapshot", "create", "--db-url", db_url])
        app(["event", "set", "completed", "True", "--db-url", db_url])
        app(["event", "get", "completed", "--db-url", db_url])
        assert "True" in capsys.readouterr().out
        app(["snapshot", "rollback", "1", "--db-url", db_url])
        app(["event", "get", "completed", "--db-url", db_url])
        assert "False" in capsys.readouterr().out
