from aimbat.lib import data, snapshot, event
from aimbat.lib.models import AimbatSnapshot, AimbatEvent
from aimbat.lib.typing import SeismogramFileType
from sqlmodel import select, Session
from pathlib import Path
import pytest
import uuid


RANDOM_COMMENT = str(uuid.uuid4())[:5]


class TestLibSnapshot:
    select_event = select(AimbatEvent).where(AimbatEvent.id == 1)
    select_snapshots = select(AimbatSnapshot)

    def test_snapshot_create_and_delete(self, test_data, db_session) -> None:  # type: ignore
        data.add_files_to_project(
            db_session, test_data, filetype=SeismogramFileType.SAC
        )

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

        snapshot.delete_snapshot(db_session, 1)
        assert len(db_session.exec(self.select_snapshots).all()) == 1
        test_snapshot = db_session.exec(self.select_snapshots).one()
        assert test_snapshot.id == 2
        with pytest.raises(ValueError):
            snapshot.delete_snapshot(db_session, 1)

    def test_snapshot_rollback(
        self, test_data: list[Path], db_session: Session
    ) -> None:
        data.add_files_to_project(
            db_session, test_data, filetype=SeismogramFileType.SAC
        )

        active_event = db_session.exec(self.select_event).one()
        event.set_active_event(db_session, active_event)
        assert event.get_active_event(db_session).id == 1
        assert db_session.exec(self.select_snapshots).all() == []

        assert active_event.parameters.completed is False

        snapshot.create_snapshot(db_session)
        test_snapshot, *_ = snapshot.get_snapshots(db_session)

        active_event.parameters.completed = True
        db_session.add(active_event)
        db_session.commit()
        assert active_event.parameters.completed is True
        snapshot.rollback_to_snapshot(db_session, test_snapshot)
        assert active_event.parameters.completed is False


class TestCliSnapshot:
    def test_sac_data(self, test_data_string, db_url, capsys) -> None:  # type: ignore
        """Test AIMBAT cli with snapshot subcommand."""

        from aimbat.app import app

        app("snapshot")
        assert "Usage" in capsys.readouterr().out

        app(["project", "create", "--db-url", db_url])

        args = ["data", "add", "--db-url", db_url]
        args.extend(test_data_string)
        app(args)

        with pytest.raises(RuntimeError):
            app(["snapshot", "create", "--db-url", db_url])

        with pytest.raises(RuntimeError):
            app(["snapshot", "list", "--db-url", db_url])

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

        app(["snapshot", "list", "--db-url", db_url])
        assert "AIMBAT snapshots for event" in capsys.readouterr().out

        app(["snapshot", "list", "--all", "--db-url", db_url])
        assert "AIMBAT snapshots for all events" in capsys.readouterr().out

        app(["snapshot", "create", "--comment", RANDOM_COMMENT, "--db-url", db_url])
        app(["snapshot", "list", "--db-url", db_url])
        assert RANDOM_COMMENT in capsys.readouterr().out

        app(["snapshot", "delete", "2", "--db-url", db_url])
        app(["snapshot", "list", "--db-url", db_url])
        assert RANDOM_COMMENT not in capsys.readouterr().out
