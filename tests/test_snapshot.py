from __future__ import annotations
from sqlmodel import Session
from pathlib import Path
from typing import TYPE_CHECKING
import pytest


if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Any
    from sqlalchemy.engine import Engine
    from pytest import CaptureFixture


RANDOM_COMMENT = "Random comment"


class TestLibSnapshotBase:
    @pytest.fixture
    def session(
        self, test_db_with_active_event: tuple[Path, str, Engine, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_active_event[3]


class TestLibSnapshotGet(TestLibSnapshotBase):
    def test_get_snapshots_when_there_are_none(self, session: Session) -> None:
        from aimbat.lib.snapshot import get_snapshots

        assert get_snapshots(session, all_events=True) == []


class TestLibSnapshotCreate(TestLibSnapshotBase):
    def test_create_snapshot(self, session: Session) -> None:
        from aimbat.lib.snapshot import get_snapshots, create_snapshot

        assert get_snapshots(session) == []
        create_snapshot(session)
        create_snapshot(session, comment=RANDOM_COMMENT)
        test_snapshot1, test_snapshot2, *_ = get_snapshots(session)
        assert test_snapshot1.comment is None
        assert test_snapshot2.comment == RANDOM_COMMENT


class TestLibSnapshotDelete(TestLibSnapshotBase):
    def test_snapshot_delete(self, session: Session) -> None:
        from aimbat.lib.snapshot import get_snapshots, create_snapshot, delete_snapshot

        create_snapshot(session)
        create_snapshot(session, comment=RANDOM_COMMENT)
        test_snapshot1, test_snapshot2, *_ = get_snapshots(session)
        delete_snapshot(session, test_snapshot1)
        assert len(get_snapshots(session)) == 1
        assert test_snapshot2 == get_snapshots(session)[0]

    def test_delete_snapshot_by_id(self, session: Session) -> None:
        from aimbat.lib.snapshot import (
            get_snapshots,
            create_snapshot,
            delete_snapshot_by_id,
        )

        create_snapshot(session)
        create_snapshot(session, comment=RANDOM_COMMENT)
        test_snapshot1, test_snapshot2, *_ = get_snapshots(session)
        delete_snapshot_by_id(session, test_snapshot1.id)
        assert len(get_snapshots(session)) == 1
        assert test_snapshot2 == get_snapshots(session)[0]

    def test_delete_snapshot_by_id_raises_with_random_id(
        self, session: Session
    ) -> None:
        from aimbat.lib.snapshot import delete_snapshot_by_id
        import uuid

        random_id = uuid.uuid4()
        with pytest.raises(ValueError):
            delete_snapshot_by_id(session, random_id)


class TestLibSnapshotRollback(TestLibSnapshotBase):
    def test_snapshot_rollback(self, session: Session) -> None:
        from aimbat.lib.snapshot import (
            get_snapshots,
            create_snapshot,
            rollback_to_snapshot,
        )
        from aimbat.lib.event import get_active_event

        active_event = get_active_event(session)

        assert active_event.parameters.completed is False
        assert active_event.seismograms[0].parameters.select is True

        create_snapshot(session)

        active_event.parameters.completed = True
        active_event.seismograms[0].parameters.select = False
        session.flush()
        assert active_event.parameters.completed is True
        assert active_event.seismograms[0].parameters.select is False

        test_snapshot, *_ = get_snapshots(session)
        rollback_to_snapshot(session, test_snapshot)
        assert active_event.parameters.completed is False
        assert active_event.seismograms[0].parameters.select is True

    def test_rollback_to_snapshot_by_id(self, session: Session) -> None:
        from aimbat.lib.snapshot import (
            get_snapshots,
            create_snapshot,
            rollback_to_snapshot_by_id,
        )

        create_snapshot(session)
        test_snapshot, *_ = get_snapshots(session)
        rollback_to_snapshot_by_id(session, test_snapshot.id)

    def test_rollback_to_snapshot_by_id_raises_with_random_id(
        self, session: Session
    ) -> None:
        from aimbat.lib.snapshot import rollback_to_snapshot_by_id
        import uuid

        random_id = uuid.uuid4()
        with pytest.raises(ValueError):
            rollback_to_snapshot_by_id(session, random_id)


class TestLibSnapshotTable(TestLibSnapshotBase):
    @pytest.fixture(autouse=True)
    def create_snapshosts(self, session: Session) -> Generator[None, Any, Any]:
        from aimbat.lib.snapshot import create_snapshot, get_snapshots

        assert get_snapshots(session) == []
        create_snapshot(session)
        create_snapshot(session, RANDOM_COMMENT)
        yield

    def test_snapshot_table_no_format(
        self, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.lib.snapshot import print_snapshot_table

        print_snapshot_table(session, format=False, print_all_events=False)
        captured = capsys.readouterr()
        assert RANDOM_COMMENT in captured.out
        assert "AIMBAT snapshots for event" in captured.out
        assert "id (shortened)" not in captured.out

    def test_snapshot_table_format(
        self, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.lib.snapshot import print_snapshot_table

        print_snapshot_table(session, format=True, print_all_events=False)
        captured = capsys.readouterr()
        assert RANDOM_COMMENT in captured.out
        assert "AIMBAT snapshots for event" in captured.out
        assert "id (shortened)" in captured.out

    def test_snapshot_table_no_format_all_events(
        self, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.lib.snapshot import print_snapshot_table

        print_snapshot_table(session, format=False, print_all_events=True)
        captured = capsys.readouterr()
        assert RANDOM_COMMENT in captured.out
        assert "AIMBAT snapshots for all events" in captured.out
        assert "id (shortened)" not in captured.out

    def test_snapshot_table_format_all_events(
        self, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.lib.snapshot import print_snapshot_table

        print_snapshot_table(session, format=True, print_all_events=True)
        captured = capsys.readouterr()
        assert RANDOM_COMMENT in captured.out
        assert "AIMBAT snapshots for all events" in captured.out
        assert "id (shortened)" in captured.out


class TestCliSnapshotBase:
    @pytest.fixture
    def db_url(
        self, test_db_with_active_event: tuple[Path, str, Engine, Session]
    ) -> Generator[str, Any, Any]:
        yield test_db_with_active_event[1]


class TestCliSnapshotUsage:
    def test_usage(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app("snapshot")
        captured = capsys.readouterr()
        assert "Usage" in captured.out


class TestCliSnapshotCreate(TestCliSnapshotBase, TestLibSnapshotBase):
    def test_create_snapshot(self, db_url: str, session: Session) -> None:
        from aimbat.app import app
        from aimbat.lib.snapshot import get_snapshots

        app(["snapshot", "create", RANDOM_COMMENT, "--db-url", db_url])

        all_snapshots = get_snapshots(session)
        assert len(all_snapshots) == 1
        assert all_snapshots[0].comment == RANDOM_COMMENT


class TestCliSnapshotRollbackAndDelete(TestCliSnapshotBase, TestLibSnapshotBase):
    @pytest.fixture(autouse=True)
    def create_snapshosts(self, session: Session) -> Generator[None, Any, Any]:
        from aimbat.lib.snapshot import create_snapshot, get_snapshots

        assert get_snapshots(session) == []
        create_snapshot(session, RANDOM_COMMENT)
        session.flush()
        yield

    def test_delete_snapshot_with_uuid(self, db_url: str, session: Session) -> None:
        from aimbat.app import app
        from aimbat.lib.snapshot import get_snapshots

        all_snapshots = get_snapshots(session)
        assert len(all_snapshots) == 1
        snapshot_id = all_snapshots[0].id

        app(["snapshot", "delete", str(snapshot_id), "--db-url", db_url])
        session.flush()
        all_snapshots = get_snapshots(session)
        assert len(all_snapshots) == 0

    def test_delete_snapshot_with_string(self, db_url: str, session: Session) -> None:
        from aimbat.app import app
        from aimbat.lib.snapshot import get_snapshots

        all_snapshots = get_snapshots(session)
        assert len(all_snapshots) == 1
        snapshot_id = str(all_snapshots[0].id)[:8]

        app(["snapshot", "delete", str(snapshot_id), "--db-url", db_url])
        session.flush()
        all_snapshots = get_snapshots(session)
        assert len(all_snapshots) == 0

    def test_rollback_to_snapshot_with_uuid(
        self, db_url: str, session: Session
    ) -> None:
        from aimbat.app import app
        from aimbat.lib.snapshot import get_snapshots

        all_snapshots = get_snapshots(session)
        assert len(all_snapshots) == 1
        snapshot_id = all_snapshots[0].id

        app(["snapshot", "rollback", str(snapshot_id), "--db-url", db_url])
        session.flush()

    def test_rollback_to_snapshot_with_string(
        self, db_url: str, session: Session
    ) -> None:
        from aimbat.app import app
        from aimbat.lib.snapshot import get_snapshots

        all_snapshots = get_snapshots(session)
        assert len(all_snapshots) == 1
        snapshot_id = str(all_snapshots[0].id)[:8]

        app(["snapshot", "rollback", str(snapshot_id), "--db-url", db_url])
        session.flush()


class TestCliSnapshotTable(TestCliSnapshotBase, TestLibSnapshotBase):
    @pytest.fixture(autouse=True)
    def create_snapshots(self, session: Session) -> Generator[None, Any, Any]:
        from aimbat.lib.snapshot import create_snapshot, get_snapshots

        assert get_snapshots(session) == []
        create_snapshot(session)
        create_snapshot(session, RANDOM_COMMENT)
        yield

    def test_snapshot_table_no_format(
        self, db_url: str, capsys: CaptureFixture
    ) -> None:
        from aimbat.app import app

        app(["snapshot", "list", "--db-url", db_url])

        captured = capsys.readouterr()
        assert RANDOM_COMMENT in captured.out
        assert "AIMBAT snapshots for event" in captured.out
        assert "id (shortened)" in captured.out
