"""Integration tests for snapshot management functions in aimbat.core._snapshot."""

import uuid

import pandas as pd
import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col, select

from aimbat.core._snapshot import (
    compute_iccs_hash,
    compute_mccc_hash,
    create_snapshot,
    delete_snapshot,
    dump_event_parameter_snapshot_table,
    dump_event_quality_snapshot_table,
    dump_seismogram_parameter_snapshot_table,
    dump_seismogram_quality_snapshot_table,
    dump_snapshot_results,
    dump_snapshot_table,
    get_snapshots,
    rollback_to_snapshot,
    sync_from_matching_hash,
)
from aimbat.models import (
    AimbatEvent,
    AimbatEventQuality,
    AimbatSeismogram,
    AimbatSeismogramParametersSnapshot,
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
    """Provides a snapshot of the event's current parameters.

    Args:
        loaded_session: The database session.

    Returns:
        An AimbatSnapshot for the event.
    """
    event = loaded_session.exec(select(AimbatEvent)).first()
    assert event is not None
    create_snapshot(loaded_session, event)
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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        assert len(loaded_session.exec(select(AimbatSnapshot)).all()) == 1

    def test_snapshot_linked_to_event(self, loaded_session: Session) -> None:
        """Verifies that the snapshot is associated with the event.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.event_id == event.id

    def test_snapshot_with_comment(self, loaded_session: Session) -> None:
        """Verifies that the optional comment is stored on the snapshot.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event, comment="test comment")
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.comment == "test comment"

    def test_snapshot_without_comment(self, loaded_session: Session) -> None:
        """Verifies that the comment defaults to None when not provided.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.comment is None

    def test_snapshot_automatic_defaults_to_false(
        self, loaded_session: Session
    ) -> None:
        """Verifies that `automatic` defaults to False when not provided.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.automatic is False

    def test_snapshot_automatic_true(self, loaded_session: Session) -> None:
        """Verifies that `automatic=True` is persisted on the snapshot.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event, automatic=True)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.automatic is True

    def test_snapshot_captures_seismogram_parameters(
        self, loaded_session: Session
    ) -> None:
        """Verifies that the snapshot includes one entry per seismogram.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        n_seismograms = len(event.seismograms)

        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_parameters_snapshots) == n_seismograms

    def test_snapshot_captures_event_parameters(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that the snapshot includes event parameters.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot for the event.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        assert snapshot.event_parameters_snapshot.parameters_id == event.parameters.id


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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        original_min_cc = snapshot.event_parameters_snapshot.min_cc

        # Mutate the parameter after taking the snapshot
        event.parameters.min_cc = 0.0
        loaded_session.add(event)
        loaded_session.commit()
        assert event.parameters.min_cc == 0.0

        rollback_to_snapshot(loaded_session, snapshot.id)
        loaded_session.refresh(event)
        assert event.parameters.min_cc == original_min_cc

    def test_rollback_restores_seismogram_parameters(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that seismogram parameters are restored to snapshot values on rollback.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        seismogram = event.seismograms[0]
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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        params = event.parameters
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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        seismogram = event.seismograms[0]
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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.parameters.select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        # Mutate a parameter (changes the hash) and overwrite quality with a different value.
        event.parameters.min_cc = 0.0
        eq = loaded_session.exec(
            select(AimbatEventQuality).where(
                col(AimbatEventQuality.event_id) == event.id
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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.parameters.select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        # Mutate a parameter (changes the hash) and overwrite quality with different values.
        event.parameters.min_cc = 0.0
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

    def test_rollback_skips_a_seismogram_deleted_after_the_snapshot(
        self, loaded_session: Session
    ) -> None:
        """A snapshot's frozen row for a since-deleted seismogram has no live
        parameter row to restore into; rollback must skip it, not crash."""
        from aimbat.core import delete_seismogram

        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        deleted_id = event.seismograms[0].id
        delete_seismogram(loaded_session, deleted_id)

        rollback_to_snapshot(loaded_session, snapshot.id)  # must not raise

        orphan = loaded_session.exec(
            select(AimbatSeismogramParametersSnapshot).where(
                col(AimbatSeismogramParametersSnapshot.seismogram_id) == deleted_id
            )
        ).one()
        assert orphan.seismogram_parameters_id is None


class TestGetSnapshots:
    """Tests for retrieving snapshots from the database."""

    def test_no_snapshots_initially(self, loaded_session: Session) -> None:
        """Verifies that no snapshots exist before any are created.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        assert len(get_snapshots(loaded_session, event_id=event.id)) == 0

    def test_get_snapshots_for_event(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that snapshots for the event are returned.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot for the event.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        snapshots = get_snapshots(loaded_session, event_id=event.id)
        assert len(snapshots) == 1
        assert snapshots[0].id == snapshot.id

    def test_get_snapshots_all_events(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that get_snapshots with all_events=True includes all events.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot for the event.
        """
        all_snapshots = get_snapshots(loaded_session)
        assert len(all_snapshots) >= 1

    def test_multiple_snapshots(self, loaded_session: Session) -> None:
        """Verifies that multiple snapshots can be created and retrieved.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event, comment="first")
        create_snapshot(loaded_session, event, comment="second")
        assert len(get_snapshots(loaded_session, event_id=event.id)) == 2


class TestComputeHashes:
    """Tests for the ICCS and MCCC parameter hashing logic."""

    def test_hashes_are_deterministic(self, loaded_session: Session) -> None:
        """The same parameters produce the same digests."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        assert compute_iccs_hash(event) == compute_iccs_hash(event)
        assert compute_mccc_hash(event) == compute_mccc_hash(event)

    def test_window_change_affects_both_hashes(self, loaded_session: Session) -> None:
        """A window change alters the signal both algorithms see."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        iccs_before, mccc_before = compute_iccs_hash(event), compute_mccc_hash(event)
        event.parameters.window_post = event.parameters.window_post + Timedelta(
            seconds=1
        )
        assert compute_iccs_hash(event) != iccs_before
        assert compute_mccc_hash(event) != mccc_before

    def test_seismogram_flip_affects_both_hashes(self, loaded_session: Session) -> None:
        """`flip` changes the stack and the MCCC inputs."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        iccs_before, mccc_before = compute_iccs_hash(event), compute_mccc_hash(event)
        event.seismograms[0].parameters.flip = not event.seismograms[0].parameters.flip
        assert compute_iccs_hash(event) != iccs_before
        assert compute_mccc_hash(event) != mccc_before

    def test_select_change_affects_iccs_hash_only(
        self, loaded_session: Session
    ) -> None:
        """`select` changes the ICCS stack but not the MCCC computation."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        iccs_before, mccc_before = compute_iccs_hash(event), compute_mccc_hash(event)
        event.seismograms[0].parameters.select = not event.seismograms[
            0
        ].parameters.select
        assert compute_iccs_hash(event) != iccs_before
        assert compute_mccc_hash(event) == mccc_before

    def test_min_cc_change_affects_neither_hash(self, loaded_session: Session) -> None:
        """`min_cc` only reaches `iccs_cc` via `select` on the next run, and
        `select` is already hashed - a bare threshold change invalidates
        nothing."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        iccs_before, mccc_before = compute_iccs_hash(event), compute_mccc_hash(event)
        event.parameters.min_cc = event.parameters.min_cc / 2 + 0.1
        assert compute_iccs_hash(event) == iccs_before
        assert compute_mccc_hash(event) == mccc_before

    def test_mccc_damp_change_affects_mccc_hash_only(
        self, loaded_session: Session
    ) -> None:
        """`mccc_damp` drives the MCCC inversion but not ICCS."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        iccs_before, mccc_before = compute_iccs_hash(event), compute_mccc_hash(event)
        event.parameters.mccc_damp = event.parameters.mccc_damp + 1.0
        assert compute_iccs_hash(event) == iccs_before
        assert compute_mccc_hash(event) != mccc_before

    def test_completed_change_affects_neither_hash(
        self, loaded_session: Session
    ) -> None:
        """`completed` is bookkeeping and excluded from both hashes."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        iccs_before, mccc_before = compute_iccs_hash(event), compute_mccc_hash(event)
        event.parameters.completed = not event.parameters.completed
        assert compute_iccs_hash(event) == iccs_before
        assert compute_mccc_hash(event) == mccc_before


class TestSyncFromMatchingHash:
    """Tests for syncing quality metrics from matching snapshots."""

    def test_syncs_mccc_quality_on_mccc_hash_match(
        self, loaded_session: Session
    ) -> None:
        """MCCC diagnostics are restored when the MCCC hash matches."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.parameters.select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session, event.id, seis_ids, select_flags, all_seismograms=True
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)
        mccc_hash = compute_mccc_hash(event)

        eq = loaded_session.exec(
            select(AimbatEventQuality).where(
                col(AimbatEventQuality.event_id) == event.id
            )
        ).one()
        eq.mccc_rmse = None
        loaded_session.add(eq)
        loaded_session.commit()

        result = sync_from_matching_hash(loaded_session, event.id, mccc_hash=mccc_hash)
        loaded_session.commit()
        assert result.mccc_synced is True
        assert result.iccs_synced is False
        loaded_session.refresh(eq)
        assert eq.mccc_rmse is not None

    def test_no_match_returns_unsynced_result(self, loaded_session: Session) -> None:
        """No candidate snapshot leaves both flags False."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        result = sync_from_matching_hash(
            loaded_session,
            event.id,
            iccs_hash="no-such-hash",
            mccc_hash="no-such-hash",
        )
        assert result == (False, False)

    def test_prefers_specified_snapshot_over_most_recent(
        self, loaded_session: Session
    ) -> None:
        """`prefer_snapshot_id` wins the tie-break over the newest candidate."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.parameters.select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session, event.id, seis_ids, select_flags, all_seismograms=True
        )
        loaded_session.refresh(event)
        eq = loaded_session.exec(
            select(AimbatEventQuality).where(
                col(AimbatEventQuality.event_id) == event.id
            )
        ).one()
        eq.mccc_rmse = pd.Timedelta(milliseconds=1)
        loaded_session.add(eq)
        loaded_session.commit()

        create_snapshot(loaded_session, event)
        snapshot1 = loaded_session.exec(select(AimbatSnapshot)).one()
        mccc_hash = compute_mccc_hash(event)

        loaded_session.refresh(eq)
        eq.mccc_rmse = pd.Timedelta(milliseconds=2)
        loaded_session.add(eq)
        loaded_session.commit()
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)

        loaded_session.refresh(eq)
        eq.mccc_rmse = None
        loaded_session.add(eq)
        loaded_session.commit()

        # Newest candidate wins with no preference (snapshot2, RMSE = 2 ms).
        sync_from_matching_hash(loaded_session, event.id, mccc_hash=mccc_hash)
        loaded_session.commit()
        loaded_session.refresh(eq)
        assert eq.mccc_rmse == pd.Timedelta(milliseconds=2)

        # Preferring snapshot1 restores the older RMSE = 1 ms.
        eq.mccc_rmse = None
        loaded_session.add(eq)
        loaded_session.commit()
        sync_from_matching_hash(
            loaded_session,
            event.id,
            mccc_hash=mccc_hash,
            prefer_snapshot_id=snapshot1.id,
        )
        loaded_session.commit()
        loaded_session.refresh(eq)
        assert eq.mccc_rmse == pd.Timedelta(milliseconds=1)

    def test_iccs_cc_not_restored_without_iccs_hash(
        self, loaded_session: Session
    ) -> None:
        """An MCCC-only sync leaves iccs_cc untouched."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        seis_ids = [s.id for s in event.seismograms]

        for seis_id in seis_ids:
            sq = AimbatSeismogramQuality(id=uuid.uuid4(), seismogram_id=seis_id)
            sq.iccs_cc = 0.75
            loaded_session.add(sq)
        loaded_session.commit()
        loaded_session.refresh(event)

        select_flags = [s.parameters.select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session, event.id, seis_ids, select_flags, all_seismograms=True
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)
        mccc_hash = compute_mccc_hash(event)

        for seis_id in seis_ids:
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality).where(
                    col(AimbatSeismogramQuality.seismogram_id) == seis_id
                )
            ).one()
            sq.iccs_cc = None
            loaded_session.add(sq)
        loaded_session.commit()

        result = sync_from_matching_hash(loaded_session, event.id, mccc_hash=mccc_hash)
        loaded_session.commit()
        assert result.iccs_synced is False
        for seis_id in seis_ids:
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality).where(
                    col(AimbatSeismogramQuality.seismogram_id) == seis_id
                )
            ).one()
            assert sq.iccs_cc is None

    def test_iccs_cc_restored_from_iccs_only_snapshot(
        self, loaded_session: Session
    ) -> None:
        """A snapshot that froze only iccs_cc still repopulates it on an ICCS match."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        seis_ids = [s.id for s in event.seismograms]

        for seis_id in seis_ids:
            sq = AimbatSeismogramQuality(id=uuid.uuid4(), seismogram_id=seis_id)
            sq.iccs_cc = 0.75
            loaded_session.add(sq)
        loaded_session.commit()
        loaded_session.refresh(event)

        # No MCCC run - this snapshot has no event quality snapshot at all.
        create_snapshot(loaded_session, event)
        iccs_hash = compute_iccs_hash(event)

        for seis_id in seis_ids:
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality).where(
                    col(AimbatSeismogramQuality.seismogram_id) == seis_id
                )
            ).one()
            sq.iccs_cc = None
            loaded_session.add(sq)
        loaded_session.commit()

        result = sync_from_matching_hash(loaded_session, event.id, iccs_hash=iccs_hash)
        loaded_session.commit()
        assert result.iccs_synced is True
        for seis_id in seis_ids:
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality).where(
                    col(AimbatSeismogramQuality.seismogram_id) == seis_id
                )
            ).one()
            assert sq.iccs_cc == 0.75

    def test_iccs_cc_not_restored_from_hash_sibling_with_different_select(
        self, loaded_session: Session
    ) -> None:
        """A snapshot taken with a different `select` set has a different ICCS
        hash, so its iccs_cc is never applied to the live records."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        seis_ids = [s.id for s in event.seismograms]

        for seis_id in seis_ids:
            sq = AimbatSeismogramQuality(id=uuid.uuid4(), seismogram_id=seis_id)
            sq.iccs_cc = 0.9
            loaded_session.add(sq)
        loaded_session.commit()
        loaded_session.refresh(event)

        # Snapshot B: one seismogram deselected.
        event.seismograms[0].parameters.select = False
        loaded_session.add(event.seismograms[0].parameters)
        loaded_session.commit()
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)

        # Back to the original selection; capture its (different) ICCS hash.
        event.seismograms[0].parameters.select = True
        loaded_session.add(event.seismograms[0].parameters)
        loaded_session.commit()
        loaded_session.refresh(event)
        iccs_hash = compute_iccs_hash(event)

        for seis_id in seis_ids:
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality).where(
                    col(AimbatSeismogramQuality.seismogram_id) == seis_id
                )
            ).one()
            sq.iccs_cc = None
            loaded_session.add(sq)
        loaded_session.commit()

        result = sync_from_matching_hash(loaded_session, event.id, iccs_hash=iccs_hash)
        loaded_session.commit()
        assert result.iccs_synced is False

    def test_only_considers_this_events_snapshots(
        self, loaded_session: Session
    ) -> None:
        """A matching hash on another event's snapshot is not used."""
        events = loaded_session.exec(select(AimbatEvent)).all()
        assert len(events) >= 2
        event, other = events[0], events[1]

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.parameters.select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session, event.id, seis_ids, select_flags, all_seismograms=True
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)
        mccc_hash = compute_mccc_hash(event)

        eq = loaded_session.exec(
            select(AimbatEventQuality).where(
                col(AimbatEventQuality.event_id) == event.id
            )
        ).one()
        eq.mccc_rmse = None
        loaded_session.add(eq)
        loaded_session.commit()

        # Ask on behalf of `other` with `event`'s hash - must not match.
        result = sync_from_matching_hash(loaded_session, other.id, mccc_hash=mccc_hash)
        assert result.mccc_synced is False


class TestDumpSnapshotTable:
    """Tests for dump_snapshot_table."""

    def test_dump_snapshot_table(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that a list is returned."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        result = dump_snapshot_table(loaded_session, event_id=event.id)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_dump_snapshot_table_read_model(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_snapshot_table with from_read_model=True."""
        result = dump_snapshot_table(loaded_session, from_read_model=True)
        assert isinstance(result, list)
        assert "seismogram_count" in result[0]

    def test_dump_snapshot_table_by_title(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_snapshot_table with by_title=True."""
        result = dump_snapshot_table(
            loaded_session, from_read_model=True, by_title=True
        )
        assert isinstance(result, list)
        assert "Time" in result[0]

    def test_dump_snapshot_table_exclude(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_snapshot_table with exclude."""
        result = dump_snapshot_table(loaded_session, exclude={"id"})
        assert "id" not in result[0]

    def test_all_events_includes_more_snapshots(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that all events returns at least as many snapshots as single event only."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        default_only = dump_snapshot_table(loaded_session, event_id=event.id)
        all_events = dump_snapshot_table(loaded_session)
        assert len(all_events) >= len(default_only)


class TestDumpEventParameterSnapshotTable:
    """Tests for dump_event_parameter_snapshot_table."""

    def test_dump_event_parameter_snapshot_table(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_event_parameter_snapshot_table."""
        result = dump_event_parameter_snapshot_table(loaded_session)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "min_cc" in result[0]
        assert "mccc_damp" in result[0]
        assert "snapshot_id" in result[0]

    def test_dump_event_parameter_snapshot_table_by_alias(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_event_parameter_snapshot_table with by_alias=True."""
        result = dump_event_parameter_snapshot_table(loaded_session, by_alias=True)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_dump_event_parameter_snapshot_table_event_id(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_event_parameter_snapshot_table filtering by event_id."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        result = dump_event_parameter_snapshot_table(loaded_session, event_id=event.id)
        assert len(result) == 1
        assert result[0]["parameters_id"] == str(event.parameters.id)

    def test_dump_event_parameter_snapshot_table_exclude(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_event_parameter_snapshot_table with exclude."""
        result = dump_event_parameter_snapshot_table(loaded_session, exclude={"id"})
        assert "id" not in result[0]


class TestDumpSeismogramParameterSnapshotTable:
    """Tests for dump_seismogram_parameter_snapshot_table."""

    def test_seismogram_parameters_count(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that seismogram_parameters count matches the event's seismograms."""
        n_seismograms = len(loaded_session.exec(select(AimbatSeismogram)).all())
        result = dump_seismogram_parameter_snapshot_table(loaded_session)
        assert len(result) <= n_seismograms

    def test_dump_seismogram_parameter_snapshot_table_by_alias(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_seismogram_parameter_snapshot_table with by_alias=True."""
        result = dump_seismogram_parameter_snapshot_table(loaded_session, by_alias=True)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_dump_seismogram_parameter_snapshot_table_exclude(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_seismogram_parameter_snapshot_table with exclude."""
        result = dump_seismogram_parameter_snapshot_table(
            loaded_session, exclude={"id"}
        )
        assert "id" not in result[0]


class TestDumpEventQualitySnapshotTable:
    """Tests for dump_event_quality_snapshot_table."""

    def test_dump_event_quality_snapshot_table_event_id(
        self, loaded_session: Session
    ) -> None:
        """Test dump_event_quality_snapshot_table filtering by event_id."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            [s.id for s in event.seismograms],
            [True] * len(event.seismograms),
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)

        result = dump_event_quality_snapshot_table(loaded_session, event_id=event.id)
        assert len(result) == 1
        assert "event_quality_id" in result[0]
        assert isinstance(result[0]["event_quality_id"], str)
        assert result[0]["event_quality_id"] is not None

    def test_dump_event_quality_snapshot_table(self, loaded_session: Session) -> None:
        """Test dump_event_quality_snapshot_table with quality data."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            [s.id for s in event.seismograms],
            [True] * len(event.seismograms),
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)

        result = dump_event_quality_snapshot_table(loaded_session)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "mccc_rmse" in result[0]


class TestDumpSeismogramQualitySnapshotTable:
    """Tests for dump_seismogram_quality_snapshot_table."""

    def test_dump_seismogram_quality_snapshot_table_event_id_with_mccc(
        self, loaded_session: Session
    ) -> None:
        """Test dump_seismogram_quality_snapshot_table filtering by event_id."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            [s.id for s in event.seismograms],
            [True] * len(event.seismograms),
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)

        result = dump_seismogram_quality_snapshot_table(
            loaded_session, event_id=event.id
        )
        assert len(result) == len(event.seismograms)
        assert "snapshot_id" in result[0]
        assert "seismogram_quality_id" in result[0]

    def test_dump_seismogram_quality_snapshot_table_exclude(
        self, loaded_session: Session
    ) -> None:
        """Test dump_seismogram_quality_snapshot_table with exclude."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            [s.id for s in event.seismograms],
            [True] * len(event.seismograms),
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)

        result = dump_seismogram_quality_snapshot_table(loaded_session, exclude={"id"})
        assert "id" not in result[0]

    def test_dump_seismogram_quality_snapshot_table(
        self, loaded_session: Session
    ) -> None:
        """Test dump_seismogram_quality_snapshot_table with quality data."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            [s.id for s in event.seismograms],
            [True] * len(event.seismograms),
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)

        result = dump_seismogram_quality_snapshot_table(loaded_session)
        assert isinstance(result, list)
        assert len(result) == len(event.seismograms)
        assert "mccc_cc_mean" in result[0]


class TestSnapshotMcccQualityRecords:
    """Tests for MCCC quality records written into snapshots."""

    def test_quality_records_written_for_all_when_true(
        self, loaded_session: Session
    ) -> None:
        """Verifies that quality records are written for every seismogram when all_seismograms=True.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        # Deselect one seismogram so the distinction between modes is meaningful.
        event.seismograms[0].parameters.select = False
        loaded_session.commit()

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.parameters.select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_quality_snapshots) == len(seis_ids)

    def test_quality_records_written_for_selected_only_when_false(
        self, loaded_session: Session
    ) -> None:
        """Verifies that quality records are only written for selected seismograms when all_seismograms=False.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        # Deselect one seismogram.
        event.seismograms[0].parameters.select = False
        loaded_session.commit()

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.parameters.select for s in event.seismograms]
        n_selected = sum(select_flags)
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            seis_ids,
            select_flags,
            all_seismograms=False,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)
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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_iccs_instance(loaded_session, event)

        for seis in event.seismograms:
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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        create_iccs_instance(loaded_session, event)
        seis = event.seismograms[0]
        loaded_session.refresh(seis)
        assert seis.quality is not None
        first_iccs_cc = seis.quality.iccs_cc

        # Force a rebuild by invalidating the cache.
        clear_iccs_cache()
        create_iccs_instance(loaded_session, event)
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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        # Write ICCS stats to the live quality table first.
        create_iccs_instance(loaded_session, event)
        loaded_session.refresh(event)

        # Create a snapshot (no MCCC has been run).
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        # Every seismogram should have an iccs_cc in the quality snapshot.
        n = len(event.seismograms)
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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        # Create snapshot with no prior ICCS run (live table is empty).
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_quality_snapshots) == 0


class TestDumpSnapshotResults:
    """Tests for dump_snapshot_results."""

    def test_returns_one_row_per_seismogram(self, loaded_session: Session) -> None:
        """Verifies that the seismograms list has one entry per seismogram in the snapshot.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        result = dump_snapshot_results(loaded_session, snapshot.id)

        assert isinstance(result, dict)
        assert len(result["seismograms"]) == len(event.seismograms)

    def test_contains_expected_envelope_fields(self, loaded_session: Session) -> None:
        """Verifies that the envelope contains the required header fields.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        result = dump_snapshot_results(loaded_session, snapshot.id)

        for field in (
            "snapshot_id",
            "snapshot_time",
            "snapshot_comment",
            "event_id",
            "event_time",
            "event_latitude",
            "event_longitude",
            "event_depth",
            "mccc_rmse",
            "seismograms",
        ):
            assert field in result, f"Expected field '{field}' in result envelope"

    def test_contains_expected_seismogram_fields(self, loaded_session: Session) -> None:
        """Verifies that each seismogram entry contains the required fields.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        result = dump_snapshot_results(loaded_session, snapshot.id)

        row = result["seismograms"][0]
        for field in (
            "seismogram_id",
            "name",
            "channel",
            "select",
            "flip",
            "t1",
            "iccs_cc",
            "mccc_cc_mean",
            "mccc_cc_std",
            "mccc_error",
        ):
            assert field in row, f"Expected field '{field}' in seismogram row"

    def test_repeated_scalars_not_in_seismogram_rows(
        self, loaded_session: Session
    ) -> None:
        """Verifies that envelope-level scalars are not duplicated in seismogram rows.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        result = dump_snapshot_results(loaded_session, snapshot.id)

        for row in result["seismograms"]:
            assert "snapshot_id" not in row
            assert "event_id" not in row
            assert "mccc_rmse" not in row

    def test_mccc_fields_null_without_mccc_run(self, loaded_session: Session) -> None:
        """Verifies that MCCC fields are null when no MCCC run was captured.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        result = dump_snapshot_results(loaded_session, snapshot.id)

        assert result["mccc_rmse"] is None
        for row in result["seismograms"]:
            assert row["mccc_cc_mean"] is None
            assert row["mccc_cc_std"] is None
            assert row["mccc_error"] is None

    def test_mccc_fields_populated_after_mccc_run(
        self, loaded_session: Session
    ) -> None:
        """Verifies that MCCC fields are present after a mock MCCC run.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.parameters.select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session, event.id, seis_ids, select_flags, all_seismograms=True
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        result = dump_snapshot_results(loaded_session, snapshot.id)

        assert result["mccc_rmse"] is not None
        assert all(row["mccc_cc_mean"] is not None for row in result["seismograms"])
        assert all(row["mccc_error"] is not None for row in result["seismograms"])

    def test_snapshot_id_not_found_raises(self, loaded_session: Session) -> None:
        """Verifies that a missing snapshot ID raises NoResultFound.

        Args:
            loaded_session: The database session.
        """
        from sqlalchemy.exc import NoResultFound

        with pytest.raises(NoResultFound):
            dump_snapshot_results(loaded_session, uuid.uuid4())

    def test_by_alias_uses_camel_case_keys(self, loaded_session: Session) -> None:
        """Verifies that by_alias=True produces camelCase field names at all levels.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        result = dump_snapshot_results(loaded_session, snapshot.id, by_alias=True)

        assert "snapshotId" in result
        assert "snapshot_id" not in result
        assert "eventTime" in result
        assert "event_time" not in result
        assert "seismogramId" in result["seismograms"][0]
        assert "seismogram_id" not in result["seismograms"][0]
