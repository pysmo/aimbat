from aimbat.app import app
from aimbat.lib import data, snapshot, event
from aimbat.lib.models import AimbatSnapshot, AimbatEvent
from aimbat.lib.typing import SeismogramFileType
from sqlmodel import select, Session
from pathlib import Path
import pytest
import uuid


RANDOM_COMMENT = str(uuid.uuid4())[:5]


class TestLibSnapshotBase:
    select_event = select(AimbatEvent).where(AimbatEvent.id == 1)
    select_snapshots = select(AimbatSnapshot)

    @pytest.fixture(autouse=True)
    def setup(self, db_session_with_project: Session, test_data: list[Path]) -> None:
        data.add_files_to_project(
            db_session_with_project, test_data, filetype=SeismogramFileType.SAC
        )


class TestLibSnapshotCreate(TestLibSnapshotBase):
    def test_create(self, db_session_with_project: Session) -> None:
        with pytest.raises(RuntimeError):
            snapshot.create_snapshot(db_session_with_project)

        active_event = db_session_with_project.exec(self.select_event).one()
        event.set_active_event(db_session_with_project, active_event)
        assert event.get_active_event(db_session_with_project).id == 1

        assert snapshot.get_snapshots(db_session_with_project) == []
        snapshot.create_snapshot(db_session_with_project)
        snapshot.create_snapshot(db_session_with_project, comment=RANDOM_COMMENT)
        test_snapshot1, test_snapshot2, *_ = snapshot.get_snapshots(
            db_session_with_project
        )
        assert test_snapshot1.id == 1
        assert test_snapshot2.id == 2
        assert test_snapshot1.comment is None
        assert test_snapshot2.comment == RANDOM_COMMENT


class TestLibSnapshotDelete(TestLibSnapshotCreate):
    def test_delete(self, db_session_with_project: Session) -> None:
        snapshot.delete_snapshot_by_id(db_session_with_project, 1)
        assert len(db_session_with_project.exec(self.select_snapshots).all()) == 1
        test_snapshot = db_session_with_project.exec(self.select_snapshots).one()
        assert test_snapshot.id == 2
        with pytest.raises(ValueError):
            snapshot.delete_snapshot_by_id(db_session_with_project, 1)


class TestLibSnapshotRollback(TestLibSnapshotCreate):
    def test_rollback(self, db_session_with_project: Session) -> None:
        active_event = db_session_with_project.exec(self.select_event).one()
        assert active_event.parameters.completed is False

        active_event.parameters.completed = True
        db_session_with_project.add(active_event)
        db_session_with_project.commit()
        assert active_event.parameters.completed is True
        test_snapshot, *_ = snapshot.get_snapshots(db_session_with_project)
        snapshot.rollback_to_snapshot(db_session_with_project, test_snapshot)
        assert active_event.parameters.completed is False


class TestCliSnapshot:
    def test_usage(self, capsys: pytest.CaptureFixture) -> None:
        app("snapshot")
        assert "Usage" in capsys.readouterr().out

    def test_with_no_active_event(self, db_url_with_data: str) -> None:
        with pytest.raises(RuntimeError):
            app(["snapshot", "create", "--db-url", db_url_with_data])

        with pytest.raises(RuntimeError):
            app(["snapshot", "list", "--db-url", db_url_with_data])

    def test_with_active_event(
        self, db_url_with_data: str, capsys: pytest.CaptureFixture
    ) -> None:
        app(["event", "activate", "1", "--db-url", db_url_with_data])

        app(["event", "get", "completed", "--db-url", db_url_with_data])
        assert "False" in capsys.readouterr().out

        app(["snapshot", "create", "--db-url", db_url_with_data])
        app(["event", "set", "completed", "True", "--db-url", db_url_with_data])
        app(["event", "get", "completed", "--db-url", db_url_with_data])
        assert "True" in capsys.readouterr().out

    def test_with_comment(
        self, db_url_with_data: str, capsys: pytest.CaptureFixture
    ) -> None:
        app(
            [
                "snapshot",
                "create",
                "--comment",
                RANDOM_COMMENT,
                "--db-url",
                db_url_with_data,
            ]
        )
        app(["snapshot", "list", "--db-url", db_url_with_data])
        assert RANDOM_COMMENT in capsys.readouterr().out

    def test_rollback(
        self, db_url_with_data: str, capsys: pytest.CaptureFixture
    ) -> None:
        app(["event", "get", "completed", "--db-url", db_url_with_data])
        assert "True" in capsys.readouterr().out
        app(["snapshot", "rollback", "1", "--db-url", db_url_with_data])
        app(["event", "get", "completed", "--db-url", db_url_with_data])
        assert "False" in capsys.readouterr().out

    def test_delete_snapshot(
        self, db_url_with_data: str, capsys: pytest.CaptureFixture
    ) -> None:
        app(["snapshot", "delete", "1", "--db-url", db_url_with_data])
        assert RANDOM_COMMENT not in capsys.readouterr().out
