"""Integration tests for snapshot management functions in aimbat.core._snapshot."""

import uuid

import pandas as pd
import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col, select

from aimbat.core import get_default_event
from aimbat.core._snapshot import (
    create_snapshot,
    delete_snapshot,
    dump_snapshot_tables,
    get_snapshots,
    rollback_to_snapshot,
)
from aimbat.models import (
    AimbatEventQuality,
    AimbatSeismogram,
    AimbatSeismogramQuality,
    AimbatSnapshot,
)


def _write_mock_mccc_quality(
    session: Session,
    event_id: uuid.UUID,
    seismogram_ids: list[uuid.UUID],
    select_flags: list[bool],
    all_seismograms: bool,
) -> None:
    """Simulate an MCCC run by writing mock quality data to the live DB tables.

    Upserts `AimbatEventQuality` and per-seismogram `AimbatSeismogramQuality`
    entries. Only seismograms indicated by `all_seismograms` / `select_flags`
    receive MCCC metric values; the rest have their MCCC fields cleared.

    Args:
        session: Database session.
        event_id: UUID of the event.
        seismogram_ids: UUIDs of the seismograms in order.
        select_flags: Per-seismogram select flag, same order as seismogram_ids.
        all_seismograms: If True, all seismograms receive MCCC data.
    """
    from aimbat.models import AimbatEventQuality, AimbatSeismogramQuality

    used_ids = {
        sid for sid, sel in zip(seismogram_ids, select_flags) if all_seismograms or sel
    }

    # Event quality
    eq = session.exec(
        select(AimbatEventQuality).where(col(AimbatEventQuality.event_id) == event_id)
    ).first()
    if eq is None:
        eq = AimbatEventQuality(
            id=uuid.uuid4(),
            event_id=event_id,
            mccc_rmse=pd.Timedelta(milliseconds=1),
        )
        session.add(eq)
    else:
        eq.mccc_rmse = pd.Timedelta(milliseconds=1)
        session.add(eq)

    # Per-seismogram quality
    for seis_id in seismogram_ids:
        sq = session.exec(
            select(AimbatSeismogramQuality).where(
                col(AimbatSeismogramQuality.seismogram_id) == seis_id
            )
        ).first()
        if sq is None:
            sq = AimbatSeismogramQuality(id=uuid.uuid4(), seismogram_id=seis_id)
            session.add(sq)
        if seis_id in used_ids:
            sq.mccc_error = pd.Timedelta(microseconds=100)
            sq.mccc_cc_mean = 0.9
            sq.mccc_cc_std = 0.05
        else:
            sq.mccc_error = None
            sq.mccc_cc_mean = None
            sq.mccc_cc_std = None
        session.add(sq)

    session.commit()


@pytest.fixture
def snapshot(loaded_session: Session) -> AimbatSnapshot:
    """Provides a snapshot of the default event's current parameters.

    Args:
        loaded_session: The database session.

    Returns:
        An AimbatSnapshot for the default event.
    """
    default_event = get_default_event(loaded_session)
    assert default_event is not None
    create_snapshot(loaded_session, default_event)
    snapshot = loaded_session.exec(select(AimbatSnapshot)).one_or_none()
    assert snapshot is not None
    return snapshot


class TestCreateSnapshot:
    """Tests for creating parameter snapshots."""

    def test_creates_snapshot(self, loaded_session: Session) -> None:
        """Verifies that a snapshot is written to the database.

        Args:
            loaded_session: The database session.
        """
        assert len(loaded_session.exec(select(AimbatSnapshot)).all()) == 0
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        create_snapshot(loaded_session, default_event)
        assert len(loaded_session.exec(select(AimbatSnapshot)).all()) == 1

    def test_snapshot_linked_to_default_event(self, loaded_session: Session) -> None:
        """Verifies that the snapshot is associated with the default event.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        create_snapshot(loaded_session, default_event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.event_id == default_event.id

    def test_snapshot_with_comment(self, loaded_session: Session) -> None:
        """Verifies that the optional comment is stored on the snapshot.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        create_snapshot(loaded_session, default_event, comment="test comment")
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.comment == "test comment"

    def test_snapshot_without_comment(self, loaded_session: Session) -> None:
        """Verifies that the comment defaults to None when not provided.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        create_snapshot(loaded_session, default_event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.comment is None

    def test_snapshot_captures_seismogram_parameters(
        self, loaded_session: Session
    ) -> None:
        """Verifies that the snapshot includes one entry per seismogram.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        n_seismograms = len(default_event.seismograms)

        create_snapshot(loaded_session, default_event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_parameters_snapshots) == n_seismograms

    def test_snapshot_captures_event_parameters(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that the snapshot includes event parameters.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot for the default event.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        assert (
            snapshot.event_parameters_snapshot.parameters_id
            == default_event.parameters.id
        )


class TestDeleteSnapshot:
    """Tests for deleting snapshots."""

    def test_delete_snapshot(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that a snapshot is removed from the database.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot to delete.
        """
        delete_snapshot(loaded_session, snapshot.id)
        assert len(loaded_session.exec(select(AimbatSnapshot)).all()) == 0

    def test_delete_snapshot_id_not_found(self, loaded_session: Session) -> None:
        """Verifies that deleting a non-existent snapshot ID raises ValueError.

        Args:
            loaded_session: The database session.
        """
        with pytest.raises(NoResultFound):
            delete_snapshot(loaded_session, uuid.uuid4())


class TestRollbackToSnapshot:
    """Tests for rolling back parameters to a snapshot."""

    def test_rollback_restores_event_parameters(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that event parameters are restored to snapshot values on rollback.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        original_min_cc = snapshot.event_parameters_snapshot.min_cc

        # Mutate the parameter after taking the snapshot
        default_event.parameters.min_cc = 0.0
        loaded_session.add(default_event)
        loaded_session.commit()
        assert default_event.parameters.min_cc == 0.0

        rollback_to_snapshot(loaded_session, snapshot.id)
        loaded_session.refresh(default_event)
        assert default_event.parameters.min_cc == original_min_cc

    def test_rollback_restores_seismogram_parameters(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that seismogram parameters are restored to snapshot values on rollback.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        seismogram = default_event.seismograms[0]
        original_select = snapshot.seismogram_parameters_snapshots[0].select

        # Mutate the parameter after taking the snapshot
        seismogram.parameters.select = not original_select
        loaded_session.add(seismogram)
        loaded_session.commit()

        rollback_to_snapshot(loaded_session, snapshot.id)
        loaded_session.refresh(seismogram)
        assert seismogram.parameters.select == original_select

    def test_rollback_restores_all_event_parameters(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that every event parameter, including timedelta fields, is restored.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        params = default_event.parameters
        snap = snapshot.event_parameters_snapshot

        # Mutate every event parameter to a value distinct from the snapshot
        params.completed = not snap.completed
        params.min_cc = 0.0 if snap.min_cc != 0.0 else 0.5
        params.window_pre = Timedelta(seconds=-1)
        params.window_post = Timedelta(seconds=1)
        params.bandpass_apply = not snap.bandpass_apply
        params.bandpass_fmin = 0.1
        params.bandpass_fmax = 1.0
        params.mccc_damp = 0.0 if snap.mccc_damp != 0.0 else 1.0
        params.mccc_min_cc = 0.0 if snap.mccc_min_cc != 0.0 else 0.5
        loaded_session.add(params)
        loaded_session.commit()

        rollback_to_snapshot(loaded_session, snapshot.id)
        loaded_session.refresh(params)

        assert params.completed == snap.completed
        assert params.min_cc == snap.min_cc
        assert params.window_pre == snap.window_pre
        assert params.window_post == snap.window_post
        assert params.bandpass_apply == snap.bandpass_apply
        assert params.bandpass_fmin == snap.bandpass_fmin
        assert params.bandpass_fmax == snap.bandpass_fmax
        assert params.mccc_damp == snap.mccc_damp
        assert params.mccc_min_cc == snap.mccc_min_cc

    def test_rollback_restores_all_seismogram_parameters(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that every seismogram parameter, including the timestamp t1, is restored.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        seismogram = default_event.seismograms[0]
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
        loaded_session.add(params)
        loaded_session.commit()

        rollback_to_snapshot(loaded_session, snapshot.id)
        loaded_session.refresh(params)

        assert params.flip == snap.flip
        assert params.select == snap.select
        assert params.t1 == snap.t1

    def test_rollback_restores_event_quality(self, loaded_session: Session) -> None:
        """Verifies that AimbatEventQuality is restored to snapshot values on rollback.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None

        seis_ids = [s.id for s in default_event.seismograms]
        select_flags = [s.select for s in default_event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            default_event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(default_event)
        create_snapshot(loaded_session, default_event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        # Mutate a parameter (changes the hash) and overwrite quality with a different value.
        default_event.parameters.min_cc = 0.0
        eq = loaded_session.exec(
            select(AimbatEventQuality).where(
                col(AimbatEventQuality.event_id) == default_event.id
            )
        ).one()
        eq.mccc_rmse = pd.Timedelta(seconds=99)
        loaded_session.add(eq)
        loaded_session.commit()

        rollback_to_snapshot(loaded_session, snapshot.id)

        loaded_session.refresh(eq)
        assert snapshot.event_quality_snapshot is not None
        assert eq.mccc_rmse == snapshot.event_quality_snapshot.mccc_rmse

    def test_rollback_restores_seismogram_quality(
        self, loaded_session: Session
    ) -> None:
        """Verifies that AimbatSeismogramQuality is restored to snapshot values on rollback.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None

        seis_ids = [s.id for s in default_event.seismograms]
        select_flags = [s.select for s in default_event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            default_event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(default_event)
        create_snapshot(loaded_session, default_event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        # Mutate a parameter (changes the hash) and overwrite quality with different values.
        default_event.parameters.min_cc = 0.0
        for seis_id in seis_ids:
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality).where(
                    col(AimbatSeismogramQuality.seismogram_id) == seis_id
                )
            ).one()
            sq.mccc_cc_mean = 0.0
            sq.mccc_error = pd.Timedelta(seconds=99)
            loaded_session.add(sq)
        loaded_session.commit()

        rollback_to_snapshot(loaded_session, snapshot.id)

        snap_quality = {
            sq.seismogram_quality_id: sq for sq in snapshot.seismogram_quality_snapshots
        }
        for seis_id in seis_ids:
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality).where(
                    col(AimbatSeismogramQuality.seismogram_id) == seis_id
                )
            ).one()
            expected = snap_quality[sq.id]
            assert sq.mccc_cc_mean == expected.mccc_cc_mean
            assert sq.mccc_error == expected.mccc_error

    def test_rollback_id_not_found(self, loaded_session: Session) -> None:
        """Verifies that rolling back to a non-existent snapshot ID raises ValueError.

        Args:
            loaded_session: The database session.
        """
        with pytest.raises(ValueError):
            rollback_to_snapshot(loaded_session, uuid.uuid4())


class TestGetSnapshots:
    """Tests for retrieving snapshots from the database."""

    def test_no_snapshots_initially(self, loaded_session: Session) -> None:
        """Verifies that no snapshots exist before any are created.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        assert len(get_snapshots(loaded_session, event_id=default_event.id)) == 0

    def test_get_snapshots_for_default_event(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that snapshots for the default event are returned.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot for the default event.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        snapshots = get_snapshots(loaded_session, event_id=default_event.id)
        assert len(snapshots) == 1
        assert snapshots[0].id == snapshot.id

    def test_get_snapshots_all_events(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that get_snapshots with all_events=True includes all events.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot for the default event.
        """
        all_snapshots = get_snapshots(loaded_session)
        assert len(all_snapshots) >= 1

    def test_multiple_snapshots(self, loaded_session: Session) -> None:
        """Verifies that multiple snapshots can be created and retrieved.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        create_snapshot(loaded_session, default_event, comment="first")
        create_snapshot(loaded_session, default_event, comment="second")
        assert len(get_snapshots(loaded_session, event_id=default_event.id)) == 2


class TestDumpSnapshotTablesToJson:
    """Tests for serialising snapshot data to JSON."""

    def test_as_dict(self, loaded_session: Session, snapshot: AimbatSnapshot) -> None:
        """Verifies that a dict is returned when as_string=False.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot to include in the dump.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        result = dump_snapshot_tables(loaded_session, event_id=default_event.id)
        assert isinstance(result, dict)
        assert "snapshots" in result
        assert len(result["snapshots"]) == 1

    def test_all_events_includes_more_snapshots(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that all_events=True returns at least as many snapshots as default only.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot to include in the dump.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        default_only = dump_snapshot_tables(loaded_session, event_id=default_event.id)
        all_events = dump_snapshot_tables(
            loaded_session,
        )
        assert len(all_events["snapshots"]) >= len(default_only["snapshots"])

    def test_seismogram_parameters_count(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that seismogram_parameters count matches the default event's seismograms.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot to include in the dump.
        """
        n_seismograms = len(loaded_session.exec(select(AimbatSeismogram)).all())
        result = dump_snapshot_tables(loaded_session)
        assert len(result["seismogram_parameters"]) <= n_seismograms


class TestSnapshotMcccQualityRecords:
    """Tests for MCCC quality records written into snapshots."""

    def test_quality_records_written_for_all_when_true(
        self, loaded_session: Session
    ) -> None:
        """Verifies that quality records are written for every seismogram when all_seismograms=True.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        # Deselect one seismogram so the distinction between modes is meaningful.
        default_event.seismograms[0].parameters.select = False
        loaded_session.commit()

        seis_ids = [s.id for s in default_event.seismograms]
        select_flags = [s.select for s in default_event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            default_event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(default_event)
        create_snapshot(loaded_session, default_event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_quality_snapshots) == len(seis_ids)

    def test_quality_records_written_for_selected_only_when_false(
        self, loaded_session: Session
    ) -> None:
        """Verifies that quality records are only written for selected seismograms when all_seismograms=False.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        # Deselect one seismogram.
        default_event.seismograms[0].parameters.select = False
        loaded_session.commit()

        seis_ids = [s.id for s in default_event.seismograms]
        select_flags = [s.select for s in default_event.seismograms]
        n_selected = sum(select_flags)
        _write_mock_mccc_quality(
            loaded_session,
            default_event.id,
            seis_ids,
            select_flags,
            all_seismograms=False,
        )
        loaded_session.refresh(default_event)
        create_snapshot(loaded_session, default_event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_quality_snapshots) == n_selected


class TestLiveQualityTable:
    """Tests for the live quality write-back and snapshot capture."""

    def test_create_iccs_instance_writes_iccs_cc(self, loaded_session: Session) -> None:
        """Verifies that calling create_iccs_instance writes iccs_cc to AimbatSeismogramQuality.

        Args:
            loaded_session: The database session.
        """
        from aimbat.core._iccs import clear_iccs_cache, create_iccs_instance

        clear_iccs_cache()
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        create_iccs_instance(loaded_session, default_event)

        for seis in default_event.seismograms:
            loaded_session.refresh(seis)
            assert seis.quality is not None
            assert seis.quality.iccs_cc is not None
            assert -1.0 <= seis.quality.iccs_cc <= 1.0

    def test_create_iccs_instance_overwrites_on_rebuild(
        self, loaded_session: Session
    ) -> None:
        """Verifies that rebuilding the ICCS instance overwrites the prior iccs_cc value.

        Args:
            loaded_session: The database session.
        """
        from aimbat.core._iccs import clear_iccs_cache, create_iccs_instance

        clear_iccs_cache()
        default_event = get_default_event(loaded_session)
        assert default_event is not None

        create_iccs_instance(loaded_session, default_event)
        seis = default_event.seismograms[0]
        loaded_session.refresh(seis)
        assert seis.quality is not None
        first_iccs_cc = seis.quality.iccs_cc

        # Force a rebuild by invalidating the cache.
        clear_iccs_cache()
        create_iccs_instance(loaded_session, default_event)
        loaded_session.refresh(seis)
        assert seis.quality is not None
        assert seis.quality.iccs_cc == first_iccs_cc

    def test_snapshot_captures_iccs_cc(self, loaded_session: Session) -> None:
        """Verifies that iccs_cc values are captured into quality snapshots when available.

        Args:
            loaded_session: The database session.
        """
        from aimbat.core._iccs import clear_iccs_cache, create_iccs_instance

        clear_iccs_cache()
        default_event = get_default_event(loaded_session)
        assert default_event is not None

        # Write ICCS stats to the live quality table first.
        create_iccs_instance(loaded_session, default_event)
        loaded_session.refresh(default_event)

        # Create a snapshot (no MCCC has been run).
        create_snapshot(loaded_session, default_event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        # Every seismogram should have an iccs_cc in the quality snapshot.
        n = len(default_event.seismograms)
        assert len(snapshot.seismogram_quality_snapshots) == n
        for q in snapshot.seismogram_quality_snapshots:
            assert q.iccs_cc is not None
            assert -1.0 <= q.iccs_cc <= 1.0
            # MCCC fields should be absent.
            assert q.mccc_cc_mean is None
            assert q.mccc_error is None

    def test_snapshot_without_iccs_stats_has_no_quality_records(
        self, loaded_session: Session
    ) -> None:
        """Verifies that a snapshot created before any ICCS run has no quality records.

        Args:
            loaded_session: The database session.
        """
        from aimbat.core._iccs import clear_iccs_cache

        clear_iccs_cache()
        default_event = get_default_event(loaded_session)
        assert default_event is not None

        # Create snapshot with no prior ICCS run (live table is empty).
        create_snapshot(loaded_session, default_event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_quality_snapshots) == 0
