"""Integration tests for snapshot management functions in aimbat.core._snapshot."""

import uuid

import pandas as pd
import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col, select

from aimbat.core import _snapshot, resolve_phase
from aimbat.core._snapshot import (
    create_snapshot,
    create_snapshots_for_added_data,
    delete_snapshot,
    dump_phase_parameter_snapshot_table,
    dump_phase_quality_snapshot_table,
    dump_seismogram_parameter_snapshot_table,
    dump_seismogram_quality_snapshot_table,
    dump_snapshot_results,
    dump_snapshot_table,
    get_snapshots,
    resync_quality,
    rollback_to_snapshot,
)
from aimbat.core._validity import Validity, compute_digests
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPhaseQuality,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersSnapshot,
    AimbatSeismogramQuality,
    AimbatSnapshot,
)

from testsupport.project import first, stamp_quality


def _write_mock_mccc_quality(
    session: Session,
    event_id: uuid.UUID,
    seismogram_ids: list[uuid.UUID],
    select_flags: list[bool],
    all_seismograms: bool,
) -> None:
    """Simulate an MCCC run by writing mock quality data to the live DB tables.

    Upserts `AimbatPhaseQuality` and per-seismogram `AimbatSeismogramQuality`
    entries. Only seismograms indicated by `all_seismograms` / `select_flags`
    receive MCCC metric values; the rest have their MCCC fields cleared.

    Args:
        session: Database session.
        event_id: UUID of the event.
        seismogram_ids: UUIDs of the seismograms in order.
        select_flags: Per-seismogram select flag, same order as seismogram_ids.
        all_seismograms: If True, all seismograms receive MCCC data.
    """
    from aimbat.models import AimbatPhaseQuality, AimbatSeismogramQuality

    used_ids = {
        sid for sid, sel in zip(seismogram_ids, select_flags) if all_seismograms or sel
    }

    # Event quality
    eq = session.exec(
        select(AimbatPhaseQuality)
        .join(AimbatPhase)
        .where(col(AimbatPhase.event_id) == event_id)
    ).first()
    if eq is None:
        eq = AimbatPhaseQuality(
            id=uuid.uuid4(),
            phase_id=resolve_phase(session, event_id).id,
            mccc_rmse=pd.Timedelta(milliseconds=1),
        )
        session.add(eq)
    else:
        eq.mccc_rmse = pd.Timedelta(milliseconds=1)
        session.add(eq)

    # Per-seismogram quality
    for seis_id in seismogram_ids:
        sq = session.exec(
            select(AimbatSeismogramQuality)
            .join(AimbatSeismogramParameters)
            .where(col(AimbatSeismogramParameters.seismogram_id) == seis_id)
        ).first()
        if sq is None:
            sq = AimbatSeismogramQuality(
                id=uuid.uuid4(),
                parameters=session.exec(
                    select(AimbatSeismogramParameters).where(
                        col(AimbatSeismogramParameters.seismogram_id) == seis_id
                    )
                ).one(),
            )
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

    stamp_quality(session, event_id)
    session.commit()


@pytest.fixture
def snapshot(loaded_session: Session) -> AimbatSnapshot:
    """Provides a snapshot of the event's current parameters.

    Args:
        loaded_session: The database session.

    Returns:
        An AimbatSnapshot for the event.
    """
    event = first(loaded_session, AimbatEvent)
    create_snapshot(loaded_session, event.phases[0].id)
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
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
        assert len(loaded_session.exec(select(AimbatSnapshot)).all()) == 1

    def test_snapshot_linked_to_event(self, loaded_session: Session) -> None:
        """Verifies that the snapshot is associated with the event.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.phase.event_id == event.id

    def test_snapshot_with_comment(self, loaded_session: Session) -> None:
        """Verifies that the optional comment is stored on the snapshot.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id, comment="test comment")
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.comment == "test comment"

    def test_snapshot_without_comment(self, loaded_session: Session) -> None:
        """Verifies that the comment defaults to None when not provided.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.comment is None

    def test_snapshot_automatic_defaults_to_false(
        self, loaded_session: Session
    ) -> None:
        """Verifies that `automatic` defaults to False when not provided.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.automatic is False

    def test_snapshot_automatic_true(self, loaded_session: Session) -> None:
        """Verifies that `automatic=True` is persisted on the snapshot.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id, automatic=True)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert snapshot.automatic is True

    def test_snapshot_captures_seismogram_parameters(
        self, loaded_session: Session
    ) -> None:
        """Verifies that the snapshot includes one entry per seismogram.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)
        n_seismograms = len(event.seismograms)

        create_snapshot(loaded_session, event.phases[0].id)
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
        event = first(loaded_session, AimbatEvent)
        assert (
            snapshot.phase_parameters_snapshot.parameters_id
            == event.phases[0].parameters.id
        )


class TestCreateSnapshotsForAddedData:
    """Tests for create_snapshots_for_added_data (the shared auto-snapshot helper)."""

    @staticmethod
    def _phases(session: Session) -> list[AimbatPhase]:
        return list(session.exec(select(AimbatPhase)).all())

    def test_snapshots_every_phase_that_gained_rows(
        self, loaded_session: Session
    ) -> None:
        """Every phase given with a positive count gets one snapshot."""
        phases = self._phases(loaded_session)

        snapshotted, failures = create_snapshots_for_added_data(
            loaded_session, {p.id: 1 for p in phases}
        )

        assert failures == []
        assert set(snapshotted) == {p.id for p in phases}
        assert len(loaded_session.exec(select(AimbatSnapshot)).all()) == len(phases)

    def test_skips_phases_without_new_rows(self, loaded_session: Session) -> None:
        """A phase with no new rows receives no snapshot."""
        phases = self._phases(loaded_session)
        untouched = phases[0]

        snapshotted, failures = create_snapshots_for_added_data(
            loaded_session, {p.id: 0 if p is untouched else 2 for p in phases}
        )

        assert failures == []
        assert untouched.id not in snapshotted
        assert set(snapshotted) == {p.id for p in phases if p is not untouched}

    @pytest.mark.parametrize(
        ("count", "comment"), [(1, "Added 1 pick"), (3, "Added 3 picks")]
    )
    def test_default_comment_counts_the_new_rows(
        self, loaded_session: Session, count: int, comment: str
    ) -> None:
        """The default comment counts the rows the phase gained."""
        phase = self._phases(loaded_session)[0]

        create_snapshots_for_added_data(loaded_session, {phase.id: count})

        snapshot = loaded_session.exec(
            select(AimbatSnapshot).where(AimbatSnapshot.phase_id == phase.id)
        ).one()
        assert snapshot.comment == comment

    def test_custom_comment_overrides_default(self, loaded_session: Session) -> None:
        """A caller-supplied comment replaces the default text."""
        phases = self._phases(loaded_session)

        create_snapshots_for_added_data(
            loaded_session, {p.id: 1 for p in phases}, comment="custom comment"
        )

        snapshots = loaded_session.exec(select(AimbatSnapshot)).all()
        assert snapshots
        assert all(s.comment == "custom comment" for s in snapshots)

    def test_one_phase_failure_does_not_block_the_others(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A snapshot failure for one phase is isolated from the rest."""
        phases = self._phases(loaded_session)
        failing_phase_id = phases[0].id

        real_create_snapshot = _snapshot.create_snapshot

        def flaky_create_snapshot(
            session: Session,
            phase_id: uuid.UUID,
            comment: str | None = None,
            automatic: bool = False,
        ) -> None:
            if phase_id == failing_phase_id:
                raise RuntimeError("boom")
            real_create_snapshot(
                session, phase_id, comment=comment, automatic=automatic
            )

        monkeypatch.setattr(_snapshot, "create_snapshot", flaky_create_snapshot)

        snapshotted, failures = create_snapshots_for_added_data(
            loaded_session, {p.id: 1 for p in phases}
        )

        assert [phase_id for phase_id, _ in failures] == [failing_phase_id]
        assert "boom" in failures[0][1]
        assert set(snapshotted) == {p.id for p in phases if p.id != failing_phase_id}
        assert len(loaded_session.exec(select(AimbatSnapshot)).all()) == len(phases) - 1

    def test_failed_flush_does_not_block_the_others(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A snapshot whose flush fails is undone without affecting the session."""
        events = loaded_session.exec(select(AimbatEvent)).all()
        phases = self._phases(loaded_session)
        failing_phase_id = events[0].phases[0].id
        failing_time = events[0].time

        real_create_snapshot = _snapshot.create_snapshot

        def clashing_create_snapshot(
            session: Session,
            phase_id: uuid.UUID,
            comment: str | None = None,
            automatic: bool = False,
        ) -> None:
            if phase_id == failing_phase_id:
                # Violates the unique constraint on the event time.
                session.add(
                    AimbatEvent(
                        time=failing_time, latitude=0.0, longitude=0.0, depth=0.0
                    )
                )
            real_create_snapshot(
                session, phase_id, comment=comment, automatic=automatic
            )

        monkeypatch.setattr(_snapshot, "create_snapshot", clashing_create_snapshot)

        snapshotted, failures = create_snapshots_for_added_data(
            loaded_session, {p.id: 1 for p in phases}
        )

        assert [phase_id for phase_id, _ in failures] == [failing_phase_id]
        assert set(snapshotted) == {p.id for p in phases if p.id != failing_phase_id}
        assert len(loaded_session.exec(select(AimbatSnapshot)).all()) == len(phases) - 1
        assert len(loaded_session.exec(select(AimbatEvent)).all()) == len(events)


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
        event = first(loaded_session, AimbatEvent)
        original_min_cc = snapshot.phase_parameters_snapshot.min_cc

        # Mutate the parameter after taking the snapshot
        event.phases[0].parameters.min_cc = 0.0
        loaded_session.add(event)
        loaded_session.commit()
        assert event.phases[0].parameters.min_cc == 0.0

        rollback_to_snapshot(loaded_session, snapshot.id)
        loaded_session.refresh(event)
        assert event.phases[0].parameters.min_cc == original_min_cc

    def test_rollback_restores_seismogram_parameters(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that seismogram parameters are restored to snapshot values on rollback.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        event = first(loaded_session, AimbatEvent)
        seismogram = event.seismograms[0]
        original_select = snapshot.seismogram_parameters_snapshots[0].select

        # Mutate the parameter after taking the snapshot
        seismogram.phase_rows[0].select = not original_select
        loaded_session.add(seismogram)
        loaded_session.commit()

        rollback_to_snapshot(loaded_session, snapshot.id)
        loaded_session.refresh(seismogram)
        assert seismogram.phase_rows[0].select == original_select

    def test_rollback_restores_all_event_parameters(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that every event parameter, including timedelta fields, is restored.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot capturing the original parameters.
        """
        event = first(loaded_session, AimbatEvent)
        params = event.phases[0].parameters
        snap = snapshot.phase_parameters_snapshot

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
        event = first(loaded_session, AimbatEvent)
        seismogram = event.seismograms[0]
        params = seismogram.phase_rows[0]
        snap = next(
            s
            for s in snapshot.seismogram_parameters_snapshots
            if s.seismogram_parameters_id == params.id
        )

        # Mutate every seismogram parameter to a value distinct from the snapshot
        params.flip = not snap.flip
        params.select = not snap.select
        params.refined_pick = Timestamp("2000-01-01", tz="UTC")
        loaded_session.add(params)
        loaded_session.commit()

        rollback_to_snapshot(loaded_session, snapshot.id)
        loaded_session.refresh(params)

        assert params.flip == snap.flip
        assert params.select == snap.select
        assert params.refined_pick == snap.refined_pick

    def test_rollback_restores_event_quality(self, loaded_session: Session) -> None:
        """Verifies that AimbatPhaseQuality is restored to snapshot values on rollback.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.phase_rows[0].select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        # Mutate a parameter (changes the hash) and overwrite quality with a different value.
        event.phases[0].parameters.min_cc = 0.0
        eq = loaded_session.exec(
            select(AimbatPhaseQuality)
            .join(AimbatPhase)
            .where(col(AimbatPhase.event_id) == event.id)
        ).one()
        eq.mccc_rmse = pd.Timedelta(seconds=99)
        loaded_session.add(eq)
        loaded_session.commit()

        rollback_to_snapshot(loaded_session, snapshot.id)

        loaded_session.refresh(eq)
        assert snapshot.phase_quality_snapshot is not None
        assert eq.mccc_rmse == snapshot.phase_quality_snapshot.mccc_rmse

    def test_rollback_restores_seismogram_quality(
        self, loaded_session: Session
    ) -> None:
        """Verifies that AimbatSeismogramQuality is restored to snapshot values on rollback.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.phase_rows[0].select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        # Mutate a parameter (changes the hash) and overwrite quality with different values.
        event.phases[0].parameters.min_cc = 0.0
        for seis_id in seis_ids:
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality)
                .join(AimbatSeismogramParameters)
                .where(col(AimbatSeismogramParameters.seismogram_id) == seis_id)
            ).one()
            sq.mccc_cc_mean = 0.0
            sq.mccc_error = pd.Timedelta(seconds=99)
            loaded_session.add(sq)
        loaded_session.commit()

        rollback_to_snapshot(loaded_session, snapshot.id)

        snap_quality = {
            sq.seismogram_parameters_id: sq
            for sq in snapshot.seismogram_quality_snapshots
        }
        for seis_id in seis_ids:
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality)
                .join(AimbatSeismogramParameters)
                .where(col(AimbatSeismogramParameters.seismogram_id) == seis_id)
            ).one()
            expected = snap_quality[sq.seismogram_parameters_id]
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

        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
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
        event = first(loaded_session, AimbatEvent)
        assert len(get_snapshots(loaded_session, event_id=event.id)) == 0

    def test_get_snapshots_for_event(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that snapshots for the event are returned.

        Args:
            loaded_session: The database session.
            snapshot: An AimbatSnapshot for the event.
        """
        event = first(loaded_session, AimbatEvent)
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
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id, comment="first")
        create_snapshot(loaded_session, event.phases[0].id, comment="second")
        assert len(get_snapshots(loaded_session, event_id=event.id)) == 2


class TestSnapshotSequence:
    """The per-event `sequence` counter, not the microsecond `time`, is the
    definitive snapshot ordering."""

    def test_back_to_back_snapshots_get_consecutive_sequences(
        self, loaded_session: Session
    ) -> None:
        """Two `create_snapshot` calls in immediate succession must not collide
        (the old microsecond-unique `time` column could)."""
        event = first(loaded_session, AimbatEvent)
        for _ in range(5):
            create_snapshot(loaded_session, event.phases[0].id)
        snaps = get_snapshots(loaded_session, event_id=event.id)
        assert sorted(s.sequence for s in snaps) == [1, 2, 3, 4, 5]

    def test_sequence_is_per_event(self, loaded_session: Session) -> None:
        """Each event numbers its own snapshots from 1."""
        events = loaded_session.exec(select(AimbatEvent)).all()
        assert len(events) >= 2
        create_snapshot(loaded_session, events[0].phases[0].id)
        create_snapshot(loaded_session, events[0].phases[0].id)
        create_snapshot(loaded_session, events[1].phases[0].id)
        assert sorted(
            s.sequence for s in get_snapshots(loaded_session, event_id=events[0].id)
        ) == [1, 2]
        assert [
            s.sequence for s in get_snapshots(loaded_session, event_id=events[1].id)
        ] == [1]


def _make_out_of_date(session: Session, event_id: uuid.UUID) -> None:
    """Mark an event's live quality as computed from other parameters."""
    rows = session.exec(
        select(AimbatSeismogramQuality)
        .join(AimbatSeismogramParameters)
        .join(AimbatSeismogram)
        .where(col(AimbatSeismogram.event_id) == event_id)
    ).all()
    for row in rows:
        row.iccs_fingerprint = "out-of-date"
    eq = session.exec(
        select(AimbatPhaseQuality)
        .join(AimbatPhase)
        .where(col(AimbatPhase.event_id) == event_id)
    ).first()
    if eq is not None:
        eq.mccc_fingerprint = "out-of-date"
    session.commit()


def _seed_quality(session: Session, event: AimbatEvent, iccs_cc: float) -> None:
    """Give every seismogram of the event a valid `iccs_cc` and MCCC values."""
    for seismogram in event.seismograms:
        session.add(
            AimbatSeismogramQuality(
                parameters=seismogram.phase_rows[0], iccs_cc=iccs_cc
            )
        )
    session.flush()
    _write_mock_mccc_quality(
        session,
        event.id,
        [s.id for s in event.seismograms],
        [s.phase_rows[0].select for s in event.seismograms],
        all_seismograms=True,
    )
    session.refresh(event)


def _iccs_ccs(session: Session, event: AimbatEvent) -> list[float | None]:
    rows = session.exec(
        select(AimbatSeismogramQuality)
        .join(AimbatSeismogramParameters)
        .join(AimbatSeismogram)
        .where(col(AimbatSeismogram.event_id) == event.id)
    ).all()
    return [row.iccs_cc for row in rows]


def _all_valid(session: Session, event: AimbatEvent) -> bool:
    validity = Validity.read(session, event_id=event.id)
    return validity.mccc(event.phases[0].id) and all(
        validity.iccs_cc(s.phase_rows[0].id) for s in event.seismograms
    )


class TestRestore:
    """`resync_quality` restores out-of-date live quality from a matching snapshot."""

    def test_restores_out_of_date_values(self, loaded_session: Session) -> None:
        event = first(loaded_session, AimbatEvent)
        _seed_quality(loaded_session, event, iccs_cc=0.75)
        create_snapshot(loaded_session, event.phases[0].id)
        _make_out_of_date(loaded_session, event.id)

        result = resync_quality(loaded_session, event.phases[0].id)

        assert result == (True, True)
        assert _all_valid(loaded_session, event)

    def test_keeps_valid_values(self, loaded_session: Session) -> None:
        """Valid live values are not replaced by an older snapshot's."""
        event = first(loaded_session, AimbatEvent)
        _seed_quality(loaded_session, event, iccs_cc=0.75)
        create_snapshot(loaded_session, event.phases[0].id)
        for row in loaded_session.exec(select(AimbatSeismogramQuality)).all():
            row.iccs_cc = 0.5
        loaded_session.commit()

        result = resync_quality(loaded_session, event.phases[0].id)

        assert result == (False, False)
        assert set(_iccs_ccs(loaded_session, event)) == {0.5}

    def test_preferred_snapshot_wins_over_valid_values(
        self, loaded_session: Session
    ) -> None:
        """A rollback restores the snapshot it rolls back to when it matches."""
        event = first(loaded_session, AimbatEvent)
        _seed_quality(loaded_session, event, iccs_cc=0.75)
        create_snapshot(loaded_session, event.phases[0].id)
        preferred = max(
            get_snapshots(loaded_session, event.id), key=lambda s: s.sequence
        )
        for row in loaded_session.exec(select(AimbatSeismogramQuality)).all():
            row.iccs_cc = 0.5
        loaded_session.commit()
        create_snapshot(loaded_session, event.phases[0].id)

        result = resync_quality(
            loaded_session, event.phases[0].id, prefer_snapshot_id=preferred.id
        )

        assert result == (True, True)
        assert set(_iccs_ccs(loaded_session, event)) == {0.75}

    @pytest.mark.parametrize("preferred", [False, True])
    def test_partial_restore_keeps_valid_values(
        self, loaded_session: Session, preferred: bool
    ) -> None:
        """Restoring one out-of-date `iccs_cc` leaves the valid ones alone, and a
        value the snapshot did not freeze never blanks a valid one."""
        event = first(loaded_session, AimbatEvent)
        kept = event.seismograms[0].phase_rows[0].id
        stale = event.seismograms[1].phase_rows[0].id
        _seed_quality(loaded_session, event, iccs_cc=0.75)
        rows = {
            row.seismogram_parameters_id: row
            for row in loaded_session.exec(select(AimbatSeismogramQuality)).all()
        }
        rows[kept].iccs_fingerprint = "out-of-date"
        loaded_session.commit()
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = max(
            get_snapshots(loaded_session, event.id), key=lambda s: s.sequence
        )

        phase_id = event.phases[0].id
        digests = compute_digests(loaded_session, phase_id)[phase_id]
        rows[kept].iccs_cc = 0.9
        rows[kept].iccs_fingerprint = digests.seismogram_cc[kept]
        rows[stale].iccs_cc = 0.1
        rows[stale].iccs_fingerprint = "out-of-date"
        loaded_session.commit()

        result = resync_quality(
            loaded_session,
            event.phases[0].id,
            prefer_snapshot_id=snapshot.id if preferred else None,
        )

        assert result.iccs_synced is True
        loaded_session.refresh(rows[kept])
        loaded_session.refresh(rows[stale])
        assert rows[kept].iccs_cc == 0.9
        assert rows[stale].iccs_cc == 0.75
        validity = Validity.read(loaded_session, event_id=event.id)
        assert validity.iccs_cc(kept) and validity.iccs_cc(stale)

    def test_no_match_restores_nothing(self, loaded_session: Session) -> None:
        event = first(loaded_session, AimbatEvent)
        _seed_quality(loaded_session, event, iccs_cc=0.75)
        _make_out_of_date(loaded_session, event.id)

        assert resync_quality(loaded_session, event.phases[0].id) == (False, False)

    def test_iccs_only_snapshot_restores_iccs_cc(self, loaded_session: Session) -> None:
        """A snapshot that froze no MCCC results still restores `iccs_cc`."""
        event = first(loaded_session, AimbatEvent)
        for seismogram in event.seismograms:
            loaded_session.add(
                AimbatSeismogramQuality(
                    parameters=seismogram.phase_rows[0], iccs_cc=0.75
                )
            )
        stamp_quality(loaded_session, event.id)
        loaded_session.commit()
        create_snapshot(loaded_session, event.phases[0].id)
        _make_out_of_date(loaded_session, event.id)

        result = resync_quality(loaded_session, event.phases[0].id)

        assert result == (False, True)
        validity = Validity.read(loaded_session, event_id=event.id)
        assert all(validity.iccs_cc(s.phase_rows[0].id) for s in event.seismograms)

    def test_snapshot_under_another_selection_does_not_match(
        self, loaded_session: Session
    ) -> None:
        """Selection is in the instance digest, so `iccs_cc` measured under
        another selection is never restored."""
        event = first(loaded_session, AimbatEvent)
        event.seismograms[0].phase_rows[0].select = False
        loaded_session.commit()
        _seed_quality(loaded_session, event, iccs_cc=0.75)
        create_snapshot(loaded_session, event.phases[0].id)

        event.seismograms[0].phase_rows[0].select = True
        loaded_session.commit()
        _make_out_of_date(loaded_session, event.id)

        result = resync_quality(loaded_session, event.phases[0].id)

        assert result.iccs_synced is False
        # Selection is not an input to MCCC, so the MCCC results do match.
        assert result.mccc_synced is True

    def test_restores_without_a_live_event_quality_row(
        self, loaded_session: Session
    ) -> None:
        event = first(loaded_session, AimbatEvent)
        _seed_quality(loaded_session, event, iccs_cc=0.75)
        create_snapshot(loaded_session, event.phases[0].id)
        loaded_session.delete(
            loaded_session.exec(
                select(AimbatPhaseQuality)
                .join(AimbatPhase)
                .where(col(AimbatPhase.event_id) == event.id)
            ).one()
        )
        loaded_session.commit()

        result = resync_quality(loaded_session, event.phases[0].id)

        assert result.mccc_synced is True
        assert Validity.read(loaded_session, event.phases[0].id).mccc(
            event.phases[0].id
        )

    def test_only_considers_this_events_snapshots(
        self, loaded_session: Session
    ) -> None:
        events = loaded_session.exec(select(AimbatEvent)).all()
        assert len(events) > 1
        event, other = events[0], events[1]
        _seed_quality(loaded_session, event, iccs_cc=0.75)
        create_snapshot(loaded_session, event.phases[0].id)
        _seed_quality(loaded_session, other, iccs_cc=0.75)
        _make_out_of_date(loaded_session, other.id)

        assert resync_quality(loaded_session, other.phases[0].id) == (False, False)

    def test_snapshot_with_an_unflushed_sub_microsecond_pick_matches(
        self, loaded_session: Session
    ) -> None:
        """The digests are taken from stored values, so a pick finer than the
        database stores does not stop the snapshot from matching."""
        event = first(loaded_session, AimbatEvent)
        picked = event.seismograms[0]
        picked.phase_rows[0].refined_pick = picked.phase_rows[
            0
        ].initial_pick + Timedelta(nanoseconds=600)
        _seed_quality(loaded_session, event, iccs_cc=0.9)
        create_snapshot(loaded_session, event.phases[0].id)
        _make_out_of_date(loaded_session, event.id)

        loaded_session.expire_all()
        assert picked.phase_rows[0].refined_pick == picked.phase_rows[
            0
        ].initial_pick + Timedelta(microseconds=1)
        assert resync_quality(loaded_session, event.phases[0].id).iccs_synced is True


class TestDumpSnapshotTable:
    """Tests for dump_snapshot_table."""

    def test_dump_snapshot_table(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Verifies that a list is returned."""
        event = first(loaded_session, AimbatEvent)
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
        event = first(loaded_session, AimbatEvent)
        default_only = dump_snapshot_table(loaded_session, event_id=event.id)
        all_events = dump_snapshot_table(loaded_session)
        assert len(all_events) >= len(default_only)


class TestDumpEventParameterSnapshotTable:
    """Tests for dump_phase_parameter_snapshot_table."""

    def test_dump_phase_parameter_snapshot_table(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_phase_parameter_snapshot_table."""
        result = dump_phase_parameter_snapshot_table(loaded_session)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "min_cc" in result[0]
        assert "mccc_damp" in result[0]
        assert "snapshot_id" in result[0]

    def test_dump_phase_parameter_snapshot_table_by_alias(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_phase_parameter_snapshot_table with by_alias=True."""
        result = dump_phase_parameter_snapshot_table(loaded_session, by_alias=True)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_dump_phase_parameter_snapshot_table_event_id(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_phase_parameter_snapshot_table filtering by event_id."""
        event = first(loaded_session, AimbatEvent)
        result = dump_phase_parameter_snapshot_table(loaded_session, event_id=event.id)
        assert len(result) == 1
        assert result[0]["parameters_id"] == str(event.phases[0].parameters.id)

    def test_dump_phase_parameter_snapshot_table_exclude(
        self, loaded_session: Session, snapshot: AimbatSnapshot
    ) -> None:
        """Test dump_phase_parameter_snapshot_table with exclude."""
        result = dump_phase_parameter_snapshot_table(loaded_session, exclude={"id"})
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
    """Tests for dump_phase_quality_snapshot_table."""

    def test_dump_phase_quality_snapshot_table_event_id(
        self, loaded_session: Session
    ) -> None:
        """Test dump_phase_quality_snapshot_table filtering by event_id."""
        event = first(loaded_session, AimbatEvent)
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            [s.id for s in event.seismograms],
            [True] * len(event.seismograms),
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)

        result = dump_phase_quality_snapshot_table(loaded_session, event_id=event.id)
        assert len(result) == 1
        assert "phase_quality_id" in result[0]
        assert isinstance(result[0]["phase_quality_id"], str)
        assert result[0]["phase_quality_id"] is not None

    def test_dump_phase_quality_snapshot_table(self, loaded_session: Session) -> None:
        """Test dump_phase_quality_snapshot_table with quality data."""
        event = first(loaded_session, AimbatEvent)
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            [s.id for s in event.seismograms],
            [True] * len(event.seismograms),
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)

        result = dump_phase_quality_snapshot_table(loaded_session)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "mccc_rmse" in result[0]


class TestDumpSeismogramQualitySnapshotTable:
    """Tests for dump_seismogram_quality_snapshot_table."""

    def test_dump_seismogram_quality_snapshot_table_event_id_with_mccc(
        self, loaded_session: Session
    ) -> None:
        """Test dump_seismogram_quality_snapshot_table filtering by event_id."""
        event = first(loaded_session, AimbatEvent)
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            [s.id for s in event.seismograms],
            [True] * len(event.seismograms),
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)

        result = dump_seismogram_quality_snapshot_table(
            loaded_session, event_id=event.id
        )
        assert len(result) == len(event.seismograms)
        assert "snapshot_id" in result[0]
        assert "seismogram_parameters_id" in result[0]

    def test_dump_seismogram_quality_snapshot_table_exclude(
        self, loaded_session: Session
    ) -> None:
        """Test dump_seismogram_quality_snapshot_table with exclude."""
        event = first(loaded_session, AimbatEvent)
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            [s.id for s in event.seismograms],
            [True] * len(event.seismograms),
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)

        result = dump_seismogram_quality_snapshot_table(loaded_session, exclude={"id"})
        assert "id" not in result[0]

    def test_dump_seismogram_quality_snapshot_table(
        self, loaded_session: Session
    ) -> None:
        """Test dump_seismogram_quality_snapshot_table with quality data."""
        event = first(loaded_session, AimbatEvent)
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            [s.id for s in event.seismograms],
            [True] * len(event.seismograms),
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)

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
        event = first(loaded_session, AimbatEvent)
        # Deselect one seismogram so the distinction between modes is meaningful.
        event.seismograms[0].phase_rows[0].select = False
        loaded_session.commit()

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.phase_rows[0].select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_quality_snapshots) == len(seis_ids)

    def test_quality_records_written_for_selected_only_when_false(
        self, loaded_session: Session
    ) -> None:
        """Verifies that quality records are only written for selected seismograms when all_seismograms=False.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)
        # Deselect one seismogram.
        event.seismograms[0].phase_rows[0].select = False
        loaded_session.commit()

        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.phase_rows[0].select for s in event.seismograms]
        n_selected = sum(select_flags)
        _write_mock_mccc_quality(
            loaded_session,
            event.id,
            seis_ids,
            select_flags,
            all_seismograms=False,
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)
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
        event = first(loaded_session, AimbatEvent)
        create_iccs_instance(loaded_session, event.phases[0].id)

        for seis in event.seismograms:
            loaded_session.refresh(seis)
            assert seis.phase_rows[0].quality is not None
            assert seis.phase_rows[0].quality.iccs_cc is not None
            assert -1.0 <= seis.phase_rows[0].quality.iccs_cc <= 1.0

    def test_create_iccs_instance_overwrites_on_rebuild(
        self, loaded_session: Session
    ) -> None:
        """Verifies that rebuilding the ICCS instance overwrites the prior iccs_cc value.

        Args:
            loaded_session: The database session.
        """
        from aimbat.core._iccs import clear_iccs_cache, create_iccs_instance

        clear_iccs_cache()
        event = first(loaded_session, AimbatEvent)

        create_iccs_instance(loaded_session, event.phases[0].id)
        seis = event.seismograms[0]
        loaded_session.refresh(seis)
        assert seis.phase_rows[0].quality is not None
        first_iccs_cc = seis.phase_rows[0].quality.iccs_cc

        # Force a rebuild by invalidating the cache.
        clear_iccs_cache()
        create_iccs_instance(loaded_session, event.phases[0].id)
        loaded_session.refresh(seis)
        assert seis.phase_rows[0].quality is not None
        assert seis.phase_rows[0].quality.iccs_cc == first_iccs_cc

    def test_snapshot_captures_iccs_cc(self, loaded_session: Session) -> None:
        """Verifies that iccs_cc values are captured into quality snapshots when available.

        Args:
            loaded_session: The database session.
        """
        from aimbat.core._iccs import clear_iccs_cache, create_iccs_instance

        clear_iccs_cache()
        event = first(loaded_session, AimbatEvent)

        # Write ICCS stats to the live quality table first.
        create_iccs_instance(loaded_session, event.phases[0].id)
        loaded_session.refresh(event)

        # Create a snapshot (no MCCC has been run).
        create_snapshot(loaded_session, event.phases[0].id)
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
        event = first(loaded_session, AimbatEvent)

        # Create snapshot with no prior ICCS run (live table is empty).
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        assert len(snapshot.seismogram_quality_snapshots) == 0


class TestDumpSnapshotResults:
    """Tests for dump_snapshot_results."""

    def test_returns_one_row_per_seismogram(self, loaded_session: Session) -> None:
        """Verifies that the seismograms list has one entry per seismogram in the snapshot.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        result = dump_snapshot_results(loaded_session, snapshot.id)

        assert isinstance(result, dict)
        assert len(result["seismograms"]) == len(event.seismograms)

    def test_contains_expected_envelope_fields(self, loaded_session: Session) -> None:
        """Verifies that the envelope contains the required header fields.

        Args:
            loaded_session: The database session.
        """
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
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
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        result = dump_snapshot_results(loaded_session, snapshot.id)

        row = result["seismograms"][0]
        for field in (
            "seismogram_id",
            "name",
            "channel",
            "select",
            "flip",
            "refined_pick",
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
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
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
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
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
        event = first(loaded_session, AimbatEvent)
        seis_ids = [s.id for s in event.seismograms]
        select_flags = [s.phase_rows[0].select for s in event.seismograms]
        _write_mock_mccc_quality(
            loaded_session, event.id, seis_ids, select_flags, all_seismograms=True
        )
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)
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
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        result = dump_snapshot_results(loaded_session, snapshot.id, by_alias=True)

        assert "snapshotId" in result
        assert "snapshot_id" not in result
        assert "eventTime" in result
        assert "event_time" not in result
        assert "seismogramId" in result["seismograms"][0]
        assert "seismogram_id" not in result["seismograms"][0]


class TestResyncQuality:
    """The restore every parameter change goes through.

    `set_phase_parameters`, `set_seismogram_parameter`,
    `reset_seismogram_parameters` and `rollback_to_snapshot` all delegate to
    `resync_quality`, so a change back to parameters a snapshot already
    measured restores its MCCC diagnostics whichever path made the change.
    The live results are made out of date in between, as a re-run under the
    changed parameters would, so a path that skips the restore fails here.
    """

    @staticmethod
    def _snapshot_with_mccc_quality(session: Session, event: AimbatEvent) -> None:
        """Give the event MCCC quality and freeze it in a snapshot."""
        _write_mock_mccc_quality(
            session,
            event.id,
            [s.id for s in event.seismograms],
            [s.phase_rows[0].select for s in event.seismograms],
            all_seismograms=True,
        )
        session.refresh(event)
        create_snapshot(session, event.phases[0].id)

    @pytest.mark.parametrize(
        "path", ["event_parameter", "seismogram_parameter", "seismogram_reset"]
    )
    def test_change_and_change_back_restores_mccc_quality(
        self, loaded_session: Session, path: str
    ) -> None:
        """Verifies each parameter-change path restores quality it can vouch for."""
        from aimbat.core._phase import set_phase_parameter
        from aimbat.core._seismogram import (
            reset_seismogram_parameters,
            set_seismogram_parameter,
        )
        from aimbat.types import PhaseParameter, SeismogramParameter

        event = first(loaded_session, AimbatEvent)
        seismogram = event.seismograms[0]
        phase_id = event.phases[0].id
        window_pre = event.phases[0].parameters.window_pre

        self._snapshot_with_mccc_quality(loaded_session, event)
        assert Validity.read(loaded_session, event.phases[0].id).mccc(
            event.phases[0].id
        )

        # Change a parameter the MCCC hash covers, then change it back.
        if path == "event_parameter":
            set_phase_parameter(
                loaded_session,
                phase_id,
                PhaseParameter.WINDOW_PRE,
                window_pre - Timedelta(seconds=1),
            )
        else:
            set_seismogram_parameter(
                loaded_session, phase_id, seismogram.id, SeismogramParameter.FLIP, True
            )

        assert not Validity.read(loaded_session, event.phases[0].id).mccc(
            event.phases[0].id
        )
        _make_out_of_date(loaded_session, event.id)

        if path == "event_parameter":
            set_phase_parameter(
                loaded_session, phase_id, PhaseParameter.WINDOW_PRE, window_pre
            )
        elif path == "seismogram_parameter":
            set_seismogram_parameter(
                loaded_session, phase_id, seismogram.id, SeismogramParameter.FLIP, False
            )
        else:
            reset_seismogram_parameters(loaded_session, phase_id, seismogram.id)

        assert Validity.read(loaded_session, event.phases[0].id).mccc(
            event.phases[0].id
        )
