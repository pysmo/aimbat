"""Quality values are stamped when written and checked when read."""

from pandas import Timedelta
from sqlmodel import Session, col, select

from aimbat.core import (
    create_iccs_instance,
    create_snapshot,
    dump_seismogram_table,
    get_phase_quality,
    resync_quality,
    rollback_to_snapshot,
    run_iccs,
    run_mccc,
)
from aimbat.core._validity import Validity, encode_members
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPhaseQuality,
    AimbatSeismogramQuality,
    AimbatSnapshot,
)

from testsupport.project import first


def _run_mccc(session: Session, event: AimbatEvent) -> None:
    iccs = create_iccs_instance(session, event.phases[0].id).iccs
    run_mccc(session, event.phases[0].id, iccs, all_seismograms=False)


def _all_valid(session: Session, event: AimbatEvent) -> bool:
    validity = Validity.read(session, event_id=event.id)
    return validity.mccc(event.phases[0].id) and all(
        validity.iccs_cc(seismogram.phase_rows[0].id)
        for seismogram in event.seismograms
    )


def _latest_snapshot(session: Session) -> AimbatSnapshot:
    snapshots = session.exec(select(AimbatSnapshot)).all()
    return max(snapshots, key=lambda s: s.sequence)


class TestStamping:
    """Values written by ICCS, MCCC and a restore match the parameters."""

    def test_building_iccs_stamps_iccs_cc(self, loaded_session: Session) -> None:
        event = first(loaded_session, AimbatEvent)
        create_iccs_instance(loaded_session, event.phases[0].id)
        loaded_session.commit()

        validity = Validity.read(loaded_session, event_id=event.id)
        assert all(validity.iccs_cc(s.phase_rows[0].id) for s in event.seismograms)

    def test_run_iccs_stamps_the_written_back_picks(
        self, loaded_session: Session
    ) -> None:
        event = first(loaded_session, AimbatEvent)
        iccs = create_iccs_instance(loaded_session, event.phases[0].id).iccs
        run_iccs(
            loaded_session, event.phases[0].id, iccs, autoflip=True, autoselect=True
        )

        validity = Validity.read(loaded_session, event_id=event.id)
        assert all(validity.iccs_cc(s.phase_rows[0].id) for s in event.seismograms)

    def test_run_mccc_records_members_and_stamps(self, loaded_session: Session) -> None:
        event = first(loaded_session, AimbatEvent)
        iccs = create_iccs_instance(loaded_session, event.phases[0].id).iccs
        result = run_mccc(
            loaded_session, event.phases[0].id, iccs, all_seismograms=False
        )

        members = {iccs.seismograms[i].extra["row_id"] for i in result.indices}
        quality = loaded_session.exec(
            select(AimbatPhaseQuality)
            .join(AimbatPhase)
            .where(col(AimbatPhase.event_id) == event.id)
        ).one()
        assert quality.mccc_members == encode_members(members)
        assert _all_valid(loaded_session, event)

    def test_restore_stamps_the_current_digests(self, loaded_session: Session) -> None:
        """Values restored from a snapshot are valid for the restored parameters."""
        event = first(loaded_session, AimbatEvent)
        _run_mccc(loaded_session, event)
        create_snapshot(loaded_session, event.phases[0].id)

        snapshot_id = _latest_snapshot(loaded_session).id

        # Run again under other parameters (MCCC also moves the picks), then
        # roll back: the live values are out of date and the snapshot matches.
        event.phases[0].parameters.window_pre -= Timedelta(seconds=1)
        loaded_session.commit()
        _run_mccc(loaded_session, event)
        rollback_to_snapshot(loaded_session, snapshot_id)

        assert _all_valid(loaded_session, event)

    def test_resync_restores_only_what_is_out_of_date(
        self, loaded_session: Session
    ) -> None:
        """Valid live values are kept, out-of-date ones restored."""
        event = first(loaded_session, AimbatEvent)
        _run_mccc(loaded_session, event)
        create_snapshot(loaded_session, event.phases[0].id)

        # Rebuilding ICCS under another window stamps `iccs_cc` for it but
        # leaves the picks, so putting the window back makes only `iccs_cc`
        # out of date.
        original = event.phases[0].parameters.window_pre
        event.phases[0].parameters.window_pre = original - Timedelta(seconds=1)
        loaded_session.commit()
        create_iccs_instance(loaded_session, event.phases[0].id)
        loaded_session.commit()
        event.phases[0].parameters.window_pre = original
        result = resync_quality(loaded_session, event.phases[0].id)

        assert result.iccs_synced
        assert not result.mccc_synced
        assert _all_valid(loaded_session, event)


class TestOutOfDateValues:
    """A value that no longer matches the parameters counts as absent."""

    def test_readers_report_them_as_absent(self, loaded_session: Session) -> None:
        event = first(loaded_session, AimbatEvent)
        _run_mccc(loaded_session, event)

        event.phases[0].parameters.window_pre -= Timedelta(seconds=1)
        loaded_session.commit()

        stored = loaded_session.exec(select(AimbatSeismogramQuality)).all()
        assert any(q.iccs_cc is not None for q in stored), (
            "Precondition: without triggers the stored values should remain."
        )
        stats = get_phase_quality(loaded_session, event.phases[0].id)
        assert stats.cc_mean is None
        assert stats.mccc_cc_mean is None
        assert stats.mccc_rmse is None
        rows = dump_seismogram_table(
            loaded_session, from_read_model=True, event_id=event.id
        )
        assert all(row["iccs_cc"] is None for row in rows)
        assert all(row["mccc_cc_mean"] is None for row in rows)

    def test_snapshot_freezes_them_as_null(self, loaded_session: Session) -> None:
        event = first(loaded_session, AimbatEvent)
        _run_mccc(loaded_session, event)

        event.phases[0].parameters.window_pre -= Timedelta(seconds=1)
        loaded_session.commit()
        create_snapshot(loaded_session, event.phases[0].id)

        snapshot = _latest_snapshot(loaded_session)
        assert snapshot.phase_quality_snapshot is None
        assert snapshot.seismogram_quality_snapshots == []

    def test_snapshot_keeps_values_a_change_leaves_valid(
        self, loaded_session: Session
    ) -> None:
        """`min_cc` is an input to nothing, so the values are still frozen."""
        event = first(loaded_session, AimbatEvent)
        _run_mccc(loaded_session, event)

        event.phases[0].parameters.min_cc /= 2
        loaded_session.commit()
        create_snapshot(loaded_session, event.phases[0].id)

        snapshot = _latest_snapshot(loaded_session)
        assert snapshot.phase_quality_snapshot is not None
        assert snapshot.phase_quality_snapshot.mccc_rmse is not None
        assert all(q.iccs_cc is not None for q in snapshot.seismogram_quality_snapshots)

    def test_rollback_to_a_snapshot_frozen_as_null_stamps_nothing(
        self, loaded_session: Session
    ) -> None:
        """The parameters come back, the quality does not."""
        event = first(loaded_session, AimbatEvent)
        _run_mccc(loaded_session, event)

        changed = event.phases[0].parameters.window_pre - Timedelta(seconds=1)
        event.phases[0].parameters.window_pre = changed
        loaded_session.commit()
        create_snapshot(loaded_session, event.phases[0].id)
        snapshot_id = _latest_snapshot(loaded_session).id
        stamps_before = {
            q.parameters.seismogram_id: q.iccs_fingerprint
            for q in loaded_session.exec(select(AimbatSeismogramQuality)).all()
        }

        event.phases[0].parameters.window_pre = changed - Timedelta(seconds=1)
        loaded_session.commit()
        rollback_to_snapshot(loaded_session, snapshot_id)

        loaded_session.refresh(event.phases[0].parameters)
        assert event.phases[0].parameters.window_pre == changed
        stamps_after = {
            q.parameters.seismogram_id: q.iccs_fingerprint
            for q in loaded_session.exec(select(AimbatSeismogramQuality)).all()
        }
        assert stamps_after == stamps_before
        validity = Validity.read(loaded_session, event_id=event.id)
        assert not validity.mccc(event.phases[0].id)
        assert not any(validity.iccs_cc(s.phase_rows[0].id) for s in event.seismograms)
