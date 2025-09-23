from __future__ import annotations
from sqlmodel import Session
from pathlib import Path
from importlib import reload
from typing import TYPE_CHECKING
import aimbat.lib.snapshot as snapshot
import pytest


if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any
    from pytest import CaptureFixture


RANDOM_COMMENT = "Random comment"


class TestSnapshotBase:
    @pytest.fixture(autouse=True)
    def reload_modules(self, test_db_with_active_event: tuple[Path, Session]) -> None:
        reload(snapshot)

    @pytest.fixture
    def session(
        self, test_db_with_active_event: tuple[Path, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_active_event[1]


class TestLibSnapshotGet(TestSnapshotBase):
    def test_get_snapshots_when_there_are_none(self, session: Session) -> None:
        assert snapshot.get_snapshots(session, all_events=True) == []


class TestLibSnapshotCreate(TestSnapshotBase):
    def test_create_snapshot(self, session: Session) -> None:
        assert snapshot.get_snapshots(session) == []
        snapshot.create_snapshot(session)
        snapshot.create_snapshot(session, comment=RANDOM_COMMENT)
        test_snapshot1, test_snapshot2, *_ = snapshot.get_snapshots(session)
        assert test_snapshot1.comment is None
        assert test_snapshot2.comment == RANDOM_COMMENT


class TestLibSnapshotDelete(TestSnapshotBase):
    def test_snapshot_delete(self, session: Session) -> None:
        snapshot.create_snapshot(session)
        snapshot.create_snapshot(session, comment=RANDOM_COMMENT)
        test_snapshot1, test_snapshot2, *_ = snapshot.get_snapshots(session)
        snapshot.delete_snapshot(session, test_snapshot1)
        assert len(snapshot.get_snapshots(session)) == 1
        assert test_snapshot2 == snapshot.get_snapshots(session)[0]

    def test_delete_snapshot_by_id(self, session: Session) -> None:
        snapshot.create_snapshot(session)
        snapshot.create_snapshot(session, comment=RANDOM_COMMENT)
        test_snapshot1, test_snapshot2, *_ = snapshot.get_snapshots(session)
        snapshot.delete_snapshot_by_id(session, test_snapshot1.id)
        assert len(snapshot.get_snapshots(session)) == 1
        assert test_snapshot2 == snapshot.get_snapshots(session)[0]

    def test_delete_snapshot_by_id_raises_with_random_id(
        self, session: Session
    ) -> None:
        import uuid

        random_id = uuid.uuid4()
        with pytest.raises(ValueError):
            snapshot.delete_snapshot_by_id(session, random_id)


class TestLibSnapshotRollback(TestSnapshotBase):
    def test_snapshot_rollback(self, session: Session) -> None:
        from aimbat.lib.event import get_active_event

        active_event = get_active_event(session)

        assert active_event.parameters.completed is False
        assert active_event.seismograms[0].parameters.select is True

        snapshot.create_snapshot(session)

        active_event.parameters.completed = True
        active_event.seismograms[0].parameters.select = False
        session.flush()
        assert active_event.parameters.completed is True
        assert active_event.seismograms[0].parameters.select is False

        test_snapshot, *_ = snapshot.get_snapshots(session)
        snapshot.rollback_to_snapshot(session, test_snapshot)
        assert active_event.parameters.completed is False
        assert active_event.seismograms[0].parameters.select is True

    def test_rollback_to_snapshot_by_id(self, session: Session) -> None:
        snapshot.create_snapshot(session)
        test_snapshot, *_ = snapshot.get_snapshots(session)
        snapshot.rollback_to_snapshot_by_id(session, test_snapshot.id)

    def test_rollback_to_snapshot_by_id_raises_with_random_id(
        self, session: Session
    ) -> None:
        import uuid

        random_id = uuid.uuid4()
        with pytest.raises(ValueError):
            snapshot.rollback_to_snapshot_by_id(session, random_id)


class TestLibSnapshotTable(TestSnapshotBase):
    @pytest.fixture(autouse=True)
    def create_snapshots(self, session: Session) -> Generator[None, Any, Any]:
        assert snapshot.get_snapshots(session) == []
        snapshot.create_snapshot(session)
        snapshot.create_snapshot(session, RANDOM_COMMENT)
        yield

    def test_snapshot_table_no_format(self, capsys: CaptureFixture) -> None:
        snapshot.print_snapshot_table(format=False, print_all_events=False)
        captured = capsys.readouterr()
        assert RANDOM_COMMENT in captured.out
        assert "AIMBAT snapshots for event" in captured.out
        assert "id (shortened)" not in captured.out

    def test_snapshot_table_format(self, capsys: CaptureFixture) -> None:
        snapshot.print_snapshot_table(format=True, print_all_events=False)
        captured = capsys.readouterr()
        assert RANDOM_COMMENT in captured.out
        assert "AIMBAT snapshots for event" in captured.out
        assert "id (shortened)" in captured.out

    def test_snapshot_table_no_format_all_events(self, capsys: CaptureFixture) -> None:
        snapshot.print_snapshot_table(format=False, print_all_events=True)
        captured = capsys.readouterr()
        assert RANDOM_COMMENT in captured.out
        assert "AIMBAT snapshots for all events" in captured.out
        assert "id (shortened)" not in captured.out

    def test_snapshot_table_format_all_events(self, capsys: CaptureFixture) -> None:
        snapshot.print_snapshot_table(format=True, print_all_events=True)
        captured = capsys.readouterr()
        assert RANDOM_COMMENT in captured.out
        assert "AIMBAT snapshots for all events" in captured.out
        assert "id (shortened)" in captured.out


class TestCliSnapshotUsage(TestSnapshotBase):
    def test_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app("snapshot")
        captured = capsys.readouterr()
        assert "Usage" in captured.out


class TestCliSnapshotCreate(TestSnapshotBase):
    def test_create_snapshot(self, session: Session) -> None:
        from aimbat.app import app

        app(["snapshot", "create", RANDOM_COMMENT])

        all_snapshots = snapshot.get_snapshots(session)
        assert len(all_snapshots) == 1
        assert all_snapshots[0].comment == RANDOM_COMMENT


class TestCliSnapshotRollbackAndDelete(TestSnapshotBase):
    @pytest.fixture(autouse=True)
    def create_snapshots(self, session: Session) -> Generator[None, Any, Any]:
        assert snapshot.get_snapshots(session) == []
        snapshot.create_snapshot(session, RANDOM_COMMENT)
        session.flush()
        yield

    def test_delete_snapshot_with_uuid(self, session: Session) -> None:
        from aimbat.app import app

        all_snapshots = snapshot.get_snapshots(session)
        assert len(all_snapshots) == 1
        snapshot_id = all_snapshots[0].id

        app(["snapshot", "delete", str(snapshot_id)])
        session.flush()
        all_snapshots = snapshot.get_snapshots(session)
        assert len(all_snapshots) == 0

    def test_delete_snapshot_with_string(self, session: Session) -> None:
        from aimbat.app import app

        all_snapshots = snapshot.get_snapshots(session)
        assert len(all_snapshots) == 1
        snapshot_id = str(all_snapshots[0].id)[:8]

        app(["snapshot", "delete", str(snapshot_id)])
        session.flush()
        all_snapshots = snapshot.get_snapshots(session)
        assert len(all_snapshots) == 0

    def test_rollback_to_snapshot_with_uuid(self, session: Session) -> None:
        from aimbat.app import app

        all_snapshots = snapshot.get_snapshots(session)
        assert len(all_snapshots) == 1
        snapshot_id = all_snapshots[0].id

        app(["snapshot", "rollback", str(snapshot_id)])
        session.flush()

    def test_rollback_to_snapshot_with_string(self, session: Session) -> None:
        from aimbat.app import app

        all_snapshots = snapshot.get_snapshots(session)
        assert len(all_snapshots) == 1
        snapshot_id = str(all_snapshots[0].id)[:8]

        app(["snapshot", "rollback", str(snapshot_id)])
        session.flush()


class TestCliSnapshotTable(TestSnapshotBase):
    @pytest.fixture(autouse=True)
    def create_snapshots(self, session: Session) -> Generator[None, Any, Any]:
        assert snapshot.get_snapshots(session) == []
        snapshot.create_snapshot(session)
        snapshot.create_snapshot(session, RANDOM_COMMENT)
        yield

    def test_snapshot_table_no_format(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["snapshot", "list"])

        captured = capsys.readouterr()
        assert RANDOM_COMMENT in captured.out
        assert "AIMBAT snapshots for event" in captured.out
        assert "id (shortened)" in captured.out
