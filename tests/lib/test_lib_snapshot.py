from importlib import reload
from sqlmodel import Session, select
from aimbat.lib.models import AimbatSnapshot
import pytest
import uuid


class TestLibSnapshot:
    def test_snapshot_create_and_delete(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, snapshot

        reload(snapshot)

        project.project_new()

        data.data_add_files([sac_file_good], filetype="sac")

        select_snapshots = select(AimbatSnapshot)

        with Session(db.engine) as session:
            assert session.exec(select_snapshots).all() == []

        with pytest.raises(RuntimeError):
            snapshot.snapshot_create(1000000)

        random_comment = str(uuid.uuid4())
        snapshot.snapshot_create(1)
        snapshot.snapshot_create(1, comment=random_comment)

        with Session(db.engine) as session:
            test_snapshot1, test_snapshot2, *_ = session.exec(select_snapshots).all()
            assert test_snapshot1.id == 1
            assert test_snapshot2.id == 2
            assert test_snapshot1.comment is None
            assert test_snapshot2.comment == random_comment

        snapshot.snapshot_delete(1)
        with Session(db.engine) as session:
            assert len(session.exec(select_snapshots).all()) == 1
            test_snapshot = session.exec(select_snapshots).one()
            assert test_snapshot.id == 2

        with pytest.raises(RuntimeError):
            snapshot.snapshot_delete(1)
