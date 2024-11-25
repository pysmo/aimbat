from sqlmodel import select
from aimbat.lib.models import AimbatSnapshot, AimbatEvent
from typer.testing import CliRunner
import pytest
import uuid


RANDOM_COMMENT = str(uuid.uuid4())[:5]


class TestLibSnapshot:
    def test_snapshot_create_and_delete(self, sac_file_good, db_session) -> None:  # type: ignore
        from aimbat.lib import data, snapshot, event

        data.add_files_to_project(db_session, [sac_file_good], filetype="sac")

        select_snapshots = select(AimbatSnapshot)
        select_event = select(AimbatEvent).where(AimbatEvent.id == 1)

        active_event = db_session.exec(select_event).one()
        event.set_active_event(db_session, active_event)
        assert db_session.exec(select_snapshots).all() == []
        snapshot.create_snapshot(db_session)
        snapshot.create_snapshot(db_session, comment=RANDOM_COMMENT)
        test_snapshot1, test_snapshot2, *_ = db_session.exec(select_snapshots).all()
        assert test_snapshot1.id == 1
        assert test_snapshot2.id == 2
        assert test_snapshot1.comment is None
        assert test_snapshot2.comment == RANDOM_COMMENT

        snapshot.delete_snapshot(db_session, 1)
        assert len(db_session.exec(select_snapshots).all()) == 1
        test_snapshot = db_session.exec(select_snapshots).one()
        assert test_snapshot.id == 2

        with pytest.raises(RuntimeError):
            snapshot.delete_snapshot(db_session, 1)


class TestCliSnapshot:
    def test_sac_data(self, sac_file_good, db_url) -> None:  # type: ignore
        """Test AIMBAT cli with snapshot subcommand."""

        from aimbat.app import app

        runner = CliRunner()
        result = runner.invoke(app, ["snapshot"])
        assert result.exit_code == 0
        assert "Usage" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "project", "create"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "data", "add", sac_file_good])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "snapshot", "create"])
        assert result.exit_code == 1

        result = runner.invoke(app, ["--db-url", db_url, "snapshot", "list"])
        assert result.exit_code == 1

        result = runner.invoke(app, ["--db-url", db_url, "event", "activate", "1"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "snapshot", "create"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "snapshot", "list"])
        assert result.exit_code == 0
        assert "AIMBAT snapshots for event" in result.output

        result = runner.invoke(app, ["--db-url", db_url, "snapshot", "list", "--all"])
        assert result.exit_code == 0
        assert "AIMBAT snapshots for all events" in result.output

        result = runner.invoke(
            app, ["--db-url", db_url, "snapshot", "create", "--comment", RANDOM_COMMENT]
        )
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "snapshot", "list"])
        assert result.exit_code == 0
        assert RANDOM_COMMENT in result.output

        result = runner.invoke(app, ["--db-url", db_url, "snapshot", "delete", "2"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["--db-url", db_url, "snapshot", "list"])
        assert result.exit_code == 0
        assert RANDOM_COMMENT not in result.output
