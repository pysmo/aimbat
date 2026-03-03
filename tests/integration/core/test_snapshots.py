"""Integration tests for snapshot management functions in aimbat.core._snapshot."""

import json
import uuid
import pytest
from pandas import Timedelta, Timestamp
from aimbat.core._snapshot import (
    create_snapshot,
    delete_snapshot,
    delete_snapshot_by_id,
    get_snapshots,
    rollback_to_snapshot,
    rollback_to_snapshot_by_id,
    dump_snapshot_tables_to_json,
    print_snapshot_table,
    print_snapshot_parameters_table,
    print_snapshot_parameters_table_by_id,
)
from aimbat.core import get_active_event
from aimbat.models import AimbatSnapshot, AimbatSeismogram
from sqlmodel import Session, select


@pytest.fixture
def session(loaded_session: Session) -> Session:
    """Provides a session with multi-event data and an active event pre-loaded.

    Args:
        loaded_session: A SQLModel Session with data populated.

    Returns:
        The database session.
    """
    return loaded_session


@pytest.fixture
def snapshot(session: Session) -> AimbatSnapshot:
    """Provides a snapshot of the active event's current parameters.

    Args:
        session: The database session.

    Returns:
        An AimbatSnapshot for the active event.
    """
    create_snapshot(session)
    return session.exec(select(AimbatSnapshot)).one()


class TestCreateSnapshot:
    """Tests for creating parameter snapshots."""

    def test_creates_snapshot(self, session: Session) -> None:
        """Verifies that a snapshot is written to the database.

        Args:
            session: The database session.
        """
        assert len(session.exec(select(AimbatSnapshot)).all()) == 0
        create_snapshot(session)
        assert len(session.exec(select(AimbatSnapshot)).all()) == 1

    def test_snapshot_linked_to_active_event(self, session: Session) -> None:
        """Verifies that the snapshot is associated with the active event.

        Args:
            session: The database session.
        """
        active_event = get_active_event(session)
        create_snapshot(session)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        assert snapshot.event_id == active_event.id

    def test_snapshot_with_comment(self, session: Session) -> None:
        """Verifies that the optional comment is stored on the snapshot.

        Args:
            session: The database session.
        """
        create_snapshot(session, comment="test comment")
        snapshot = session.exec(select(AimbatSnapshot)).one()
        assert snapshot.comment == "test comment"

    def test_snapshot_without_comment(self, session: Session) -> None:
        """Verifies that the comment defaults to None when not provided.

        Args:
            session: The database session.
        """
        create_snapshot(session)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        assert snapshot.comment is None

    def test_snapshot_captures_seismogram_parameters(self, session: Session) -> None:
        """Verifies that the snapshot includes one entry per seismogram.

        Args:
            session: The database session.
        """
        active_event = get_active_event(session)
        n_seismograms = len(active_event.seismograms)

        create_snapshot(session)
        snapshot = session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_parameters_snapshots) == n_seismograms

    def test_snapshot_captures_event_parameters(
        self, session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that the snapshot includes event parameters.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot for the active event.
        """
        active_event = get_active_event(session)
        assert (
            snapshot.event_parameters_snapshot.parameters_id
            == active_event.parameters.id
        )


class TestDeleteSnapshot:
    """Tests for deleting snapshots."""

    def test_delete_snapshot(self, session: Session, snapshot: AimbatSnapshot) -> None:
        """Verifies that a snapshot is removed from the database.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot to delete.
        """
        delete_snapshot(session, snapshot)
        assert len(session.exec(select(AimbatSnapshot)).all()) == 0

    def test_delete_snapshot_by_id(
        self, session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that a snapshot is removed when deleted by ID.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot whose ID is used for deletion.
        """
        delete_snapshot_by_id(session, snapshot.id)
        assert session.get(AimbatSnapshot, snapshot.id) is None

    def test_delete_snapshot_by_id_not_found(self, session: Session) -> None:
        """Verifies that deleting a non-existent snapshot ID raises ValueError.

        Args:
            session: The database session.
        """
        with pytest.raises(ValueError):
            delete_snapshot_by_id(session, uuid.uuid4())


class TestRollbackToSnapshot:
    """Tests for rolling back parameters to a snapshot."""

    def test_rollback_restores_event_parameters(
        self, session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that event parameters are restored to snapshot values on rollback.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        active_event = get_active_event(session)
        original_min_ccnorm = snapshot.event_parameters_snapshot.min_ccnorm

        # Mutate the parameter after taking the snapshot
        active_event.parameters.min_ccnorm = 0.0
        session.add(active_event)
        session.commit()
        assert active_event.parameters.min_ccnorm == 0.0

        rollback_to_snapshot(session, snapshot)
        session.refresh(active_event)
        assert active_event.parameters.min_ccnorm == original_min_ccnorm

    def test_rollback_restores_seismogram_parameters(
        self, session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that seismogram parameters are restored to snapshot values on rollback.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        active_event = get_active_event(session)
        seismogram = active_event.seismograms[0]
        original_select = snapshot.seismogram_parameters_snapshots[0].select

        # Mutate the parameter after taking the snapshot
        seismogram.parameters.select = not original_select
        session.add(seismogram)
        session.commit()

        rollback_to_snapshot(session, snapshot)
        session.refresh(seismogram)
        assert seismogram.parameters.select == original_select

    def test_rollback_by_id(self, session: Session, snapshot: AimbatSnapshot) -> None:
        """Verifies that rollback_to_snapshot_by_id produces the same result as rollback_to_snapshot.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot to roll back to.
        """
        active_event = get_active_event(session)
        original_min_ccnorm = snapshot.event_parameters_snapshot.min_ccnorm

        active_event.parameters.min_ccnorm = 0.0
        session.add(active_event)
        session.commit()

        rollback_to_snapshot_by_id(session, snapshot.id)
        session.refresh(active_event)
        assert active_event.parameters.min_ccnorm == original_min_ccnorm

    def test_rollback_restores_all_event_parameters(
        self, session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that every event parameter, including timedelta fields, is restored.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        active_event = get_active_event(session)
        params = active_event.parameters
        snap = snapshot.event_parameters_snapshot

        # Mutate every event parameter to a value distinct from the snapshot
        params.completed = not snap.completed
        params.min_ccnorm = 0.0 if snap.min_ccnorm != 0.0 else 0.5
        params.window_pre = Timedelta(seconds=-1)
        params.window_post = Timedelta(seconds=1)
        params.bandpass_apply = not snap.bandpass_apply
        params.bandpass_fmin = 0.1
        params.bandpass_fmax = 1.0
        params.mccc_damp = 0.0 if snap.mccc_damp != 0.0 else 1.0
        params.mccc_min_ccnorm = 0.0 if snap.mccc_min_ccnorm != 0.0 else 0.5
        session.add(params)
        session.commit()

        rollback_to_snapshot(session, snapshot)
        session.refresh(params)

        assert params.completed == snap.completed
        assert params.min_ccnorm == snap.min_ccnorm
        assert params.window_pre == snap.window_pre
        assert params.window_post == snap.window_post
        assert params.bandpass_apply == snap.bandpass_apply
        assert params.bandpass_fmin == snap.bandpass_fmin
        assert params.bandpass_fmax == snap.bandpass_fmax
        assert params.mccc_damp == snap.mccc_damp
        assert params.mccc_min_ccnorm == snap.mccc_min_ccnorm

    def test_rollback_restores_all_seismogram_parameters(
        self, session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that every seismogram parameter, including the timestamp t1, is restored.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        active_event = get_active_event(session)
        seismogram = active_event.seismograms[0]
        params = seismogram.parameters
        snap = next(
            s
            for s in snapshot.seismogram_parameters_snapshots
            if s.seismogram_parameters_id == params.id
        )

        # Mutate every seismogram parameter to a value distinct from the snapshot
        params.flip = not snap.flip
        params.select = not snap.select
        params.t1 = Timestamp("2000-01-01", tz="UTC")
        session.add(params)
        session.commit()

        rollback_to_snapshot(session, snapshot)
        session.refresh(params)

        assert params.flip == snap.flip
        assert params.select == snap.select
        assert params.t1 == snap.t1

    def test_rollback_by_id_not_found(self, session: Session) -> None:
        """Verifies that rolling back to a non-existent snapshot ID raises ValueError.

        Args:
            session: The database session.
        """
        with pytest.raises(ValueError):
            rollback_to_snapshot_by_id(session, uuid.uuid4())


class TestGetSnapshots:
    """Tests for retrieving snapshots from the database."""

    def test_no_snapshots_initially(self, session: Session) -> None:
        """Verifies that no snapshots exist before any are created.

        Args:
            session: The database session.
        """
        assert len(get_snapshots(session)) == 0

    def test_get_snapshots_for_active_event(
        self, session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that snapshots for the active event are returned.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot for the active event.
        """
        snapshots = get_snapshots(session, all_events=False)
        assert len(snapshots) == 1
        assert snapshots[0].id == snapshot.id

    def test_get_snapshots_all_events(
        self, session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that get_snapshots with all_events=True includes all events.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot for the active event.
        """
        all_snapshots = get_snapshots(session, all_events=True)
        assert len(all_snapshots) >= 1

    def test_multiple_snapshots(self, session: Session) -> None:
        """Verifies that multiple snapshots can be created and retrieved.

        Args:
            session: The database session.
        """
        create_snapshot(session, comment="first")
        create_snapshot(session, comment="second")
        assert len(get_snapshots(session)) == 2


class TestDumpSnapshotTablesToJson:
    """Tests for serialising snapshot data to JSON."""

    def test_as_string(self, session: Session, snapshot: AimbatSnapshot) -> None:
        """Verifies that a JSON string is returned when as_string=True.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot to include in the dump.
        """
        result = dump_snapshot_tables_to_json(session, all_events=False, as_string=True)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "snapshots" in parsed
        assert "event_parameters" in parsed
        assert "seismogram_parameters" in parsed

    def test_as_dict(self, session: Session, snapshot: AimbatSnapshot) -> None:
        """Verifies that a dict is returned when as_string=False.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot to include in the dump.
        """
        result = dump_snapshot_tables_to_json(
            session, all_events=False, as_string=False
        )
        assert isinstance(result, dict)
        assert "snapshots" in result
        assert len(result["snapshots"]) == 1

    def test_all_events_includes_more_snapshots(
        self, session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that all_events=True returns at least as many snapshots as active only.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot to include in the dump.
        """
        active_only = dump_snapshot_tables_to_json(
            session, all_events=False, as_string=False
        )
        all_events = dump_snapshot_tables_to_json(
            session, all_events=True, as_string=False
        )
        assert len(all_events["snapshots"]) >= len(active_only["snapshots"])

    def test_seismogram_parameters_count(
        self, session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that seismogram_parameters count matches the active event's seismograms.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot to include in the dump.
        """
        n_seismograms = len(session.exec(select(AimbatSeismogram)).all())
        result = dump_snapshot_tables_to_json(session, all_events=True, as_string=False)
        assert len(result["seismogram_parameters"]) <= n_seismograms


class TestPrintSnapshotParametersTable:
    """Tests for printing the snapshot parameters table."""

    def test_print_short(
        self,
        session: Session,
        snapshot: AimbatSnapshot,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Verifies that output is produced with short=True.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot whose event parameters are displayed.
            capsys: The pytest capsys fixture.
        """
        print_snapshot_parameters_table(
            session, snapshot.event_parameters_snapshot, short=True
        )
        assert len(capsys.readouterr().out) > 0

    def test_print_long(
        self,
        session: Session,
        snapshot: AimbatSnapshot,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Verifies that output is produced with short=False.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot whose event parameters are displayed.
            capsys: The pytest capsys fixture.
        """
        print_snapshot_parameters_table(
            session, snapshot.event_parameters_snapshot, short=False
        )
        assert len(capsys.readouterr().out) > 0

    def test_print_by_id_short(
        self,
        session: Session,
        snapshot: AimbatSnapshot,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Verifies that output is produced when looking up by snapshot ID with short=True.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot whose ID is used for lookup.
            capsys: The pytest capsys fixture.
        """
        print_snapshot_parameters_table_by_id(session, snapshot.id, short=True)
        assert len(capsys.readouterr().out) > 0

    def test_print_by_id_long(
        self,
        session: Session,
        snapshot: AimbatSnapshot,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Verifies that output is produced when looking up by snapshot ID with short=False.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot whose ID is used for lookup.
            capsys: The pytest capsys fixture.
        """
        print_snapshot_parameters_table_by_id(session, snapshot.id, short=False)
        assert len(capsys.readouterr().out) > 0

    def test_print_by_id_not_found(self, session: Session) -> None:
        """Verifies that a ValueError is raised for an unknown snapshot ID.

        Args:
            session: The database session.
        """
        with pytest.raises(ValueError):
            print_snapshot_parameters_table_by_id(session, uuid.uuid4(), short=False)


class TestPrintSnapshotTable:
    """Tests for printing the snapshot table."""

    def test_print_active_event_short(
        self,
        session: Session,
        snapshot: AimbatSnapshot,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Verifies that output is produced for the active event with short=True.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot to display.
            capsys: The pytest capsys fixture.
        """
        print_snapshot_table(session, short=True, all_events=False)
        assert len(capsys.readouterr().out) > 0

    def test_print_active_event_long(
        self,
        session: Session,
        snapshot: AimbatSnapshot,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Verifies that output is produced for the active event with short=False.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot to display.
            capsys: The pytest capsys fixture.
        """
        print_snapshot_table(session, short=False, all_events=False)
        assert len(capsys.readouterr().out) > 0

    def test_print_all_events(
        self,
        session: Session,
        snapshot: AimbatSnapshot,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Verifies that output is produced when printing snapshots for all events.

        Args:
            session: The database session.
            snapshot: An AimbatSnapshot to display.
            capsys: The pytest capsys fixture.
        """
        print_snapshot_table(session, short=False, all_events=True)
        assert len(capsys.readouterr().out) > 0
