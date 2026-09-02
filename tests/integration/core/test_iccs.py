"""Integration tests for ICCS alignment and MCCC quality clearing."""

from sqlmodel import Session, select

from aimbat.core import (
    build_iccs_from_snapshot,
    cc_stats,
    create_iccs_instance,
    create_snapshot,
    run_iccs,
    run_mccc,
)
from aimbat.models import AimbatEvent, AimbatSeismogramQuality, AimbatSnapshot


class TestIccsMcccInterplay:
    """Tests for ICCS alignment affecting MCCC quality stats."""

    def test_run_iccs_nulls_mccc_stats_on_change(self, loaded_session: Session) -> None:
        """Verifies that running ICCS nulls MCCC stats if t1 changed."""
        from pandas import Timedelta

        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        # 1. Run MCCC to populate quality stats
        iccs_bound = create_iccs_instance(loaded_session, event)
        run_mccc(loaded_session, event, iccs_bound.iccs, all_seismograms=False)

        # Verify stats are present
        loaded_session.refresh(event)
        assert event.quality is not None
        assert event.quality.mccc_rmse is not None

        # Ensure at least one seismogram has MCCC stats
        seis_quality = loaded_session.exec(select(AimbatSeismogramQuality)).first()
        assert seis_quality is not None
        assert seis_quality.mccc_cc_mean is not None

        # 2. Modify t1 for one seismogram to ensure ICCS will change it
        seis = event.seismograms[0]
        assert seis.parameters.t1 is not None
        seis.parameters.t1 += Timedelta(seconds=0.1)  # Nudge by 0.1s
        loaded_session.add(seis.parameters)
        loaded_session.commit()
        loaded_session.refresh(event)

        # 3. Run ICCS
        iccs_bound = create_iccs_instance(loaded_session, event)
        run_iccs(
            loaded_session, event, iccs_bound.iccs, autoflip=False, autoselect=False
        )

        # 4. Verify MCCC stats are nulled
        loaded_session.refresh(event)
        if event.quality:
            assert event.quality.mccc_rmse is None

        # Check all seismograms of this event
        for s in event.seismograms:
            if s.quality:
                assert s.quality.mccc_cc_mean is None
                assert s.quality.mccc_cc_std is None
                assert s.quality.mccc_error is None

    def test_run_iccs_preserves_mccc_stats_on_no_change(
        self, loaded_session: Session
    ) -> None:
        """Verifies that running ICCS preserves MCCC stats if t1 did not change."""
        from uuid import uuid4

        from pandas import Timedelta

        from aimbat.models import AimbatEventQuality

        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        # 1. Run ICCS first to ensure alignment
        iccs_bound = create_iccs_instance(loaded_session, event)
        run_iccs(
            loaded_session, event, iccs_bound.iccs, autoflip=False, autoselect=False
        )
        loaded_session.refresh(event)

        # 2. Manually populate MCCC quality stats (to avoid MCCC moving t1)
        if event.quality is None:
            event.quality = AimbatEventQuality(id=uuid4(), event_id=event.id)
        event.quality.mccc_rmse = Timedelta(seconds=0.01)
        loaded_session.add(event.quality)

        for seis in event.seismograms:
            if seis.quality is None:
                from aimbat.models import AimbatSeismogramQuality

                seis.quality = AimbatSeismogramQuality(
                    id=uuid4(), seismogram_id=seis.id
                )
            seis.quality.mccc_cc_mean = 0.99
            loaded_session.add(seis.quality)

        loaded_session.commit()
        loaded_session.refresh(event)

        assert event.quality.mccc_rmse is not None
        initial_rmse = event.quality.mccc_rmse

        # 3. Run ICCS again (should result in no change since already aligned)
        iccs_bound = create_iccs_instance(loaded_session, event)
        run_iccs(
            loaded_session, event, iccs_bound.iccs, autoflip=False, autoselect=False
        )
        loaded_session.refresh(event)

        # 4. Verify MCCC stats remain
        assert event.quality is not None
        assert event.quality.mccc_rmse == initial_rmse

        for s in event.seismograms:
            assert s.quality is not None
            assert s.quality.mccc_cc_mean == 0.99

    def test_run_iccs_t1_change_nulls_all_iccs_cc(
        self, loaded_session: Session
    ) -> None:
        """Verifies that changing t1 on a selected seismogram nulls iccs_cc for all seismograms.

        t1 affects the stack, so all iccs_cc values become stale when it changes
        on a selected seismogram.
        """
        from pandas import Timedelta

        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        # 1. Run ICCS to populate iccs_cc
        iccs_bound = create_iccs_instance(loaded_session, event)
        run_iccs(
            loaded_session, event, iccs_bound.iccs, autoflip=False, autoselect=False
        )
        loaded_session.refresh(event)

        # Store initial ICCS CCs
        initial_ccs = {s.id: s.quality.iccs_cc for s in event.seismograms if s.quality}
        assert len(initial_ccs) > 1

        # 2. Change t1 on a selected seismogram — trigger 7b fires, stack is changed
        seis_to_change = event.seismograms[0]
        assert seis_to_change.parameters.select is True
        assert seis_to_change.parameters.t1 is not None
        seis_to_change.parameters.t1 += Timedelta(seconds=0.1)
        loaded_session.add(seis_to_change.parameters)
        loaded_session.commit()
        loaded_session.refresh(event)

        # 3. Verify iccs_cc is nulled for ALL seismograms (stack changed)
        for s in event.seismograms:
            if s.id in initial_ccs:
                assert s.quality is not None
                assert s.quality.iccs_cc is None

    def test_run_iccs_refreshes_min_cc_from_db(self, loaded_session: Session) -> None:
        """A `min_cc` change does not rebuild the ICCS instance (it is not a
        stack change), so `run_iccs` must refresh the autoselect threshold on
        the instance before running - otherwise an autoselect run uses the
        stale value baked in at construction."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        iccs_bound = create_iccs_instance(loaded_session, event)
        assert iccs_bound.iccs.min_cc == event.parameters.min_cc

        event.parameters.min_cc = 0.123
        loaded_session.add(event.parameters)
        loaded_session.commit()

        # The instance is unchanged by the bare threshold edit...
        assert not iccs_bound.is_stale(event)
        assert iccs_bound.iccs.min_cc != 0.123

        # ...but run_iccs picks it up.
        run_iccs(
            loaded_session, event, iccs_bound.iccs, autoflip=False, autoselect=True
        )
        assert iccs_bound.iccs.min_cc == 0.123


class TestCcStats:
    """Tests for `core.cc_stats`."""

    def test_counts_and_selection(self, loaded_session: Session) -> None:
        """Verifies n_all/n_selected track the ICCS instance's seismograms
        and that deselecting one drops it from the selected stats only.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        iccs_bound = create_iccs_instance(loaded_session, event)
        iccs = iccs_bound.iccs

        stats = cc_stats(iccs)
        assert stats.n_all == len(iccs.seismograms)
        assert stats.n_selected == sum(1 for s in iccs.seismograms if s.select)
        assert stats.mean_all is not None
        assert -1.0 <= stats.mean_all <= 1.0
        assert stats.n_selected > 1

        iccs.seismograms[0].select = False
        iccs.clear_cache()
        new_stats = cc_stats(iccs)
        assert new_stats.n_all == stats.n_all
        assert new_stats.n_selected == stats.n_selected - 1

    def test_sem_is_none_for_single_value(self, loaded_session: Session) -> None:
        """Verifies SEM is None when fewer than two values are available."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        iccs_bound = create_iccs_instance(loaded_session, event)
        iccs = iccs_bound.iccs
        for i, seis in enumerate(iccs.seismograms):
            seis.select = i == 0
        iccs.clear_cache()

        stats = cc_stats(iccs)
        assert stats.n_selected == 1
        assert stats.mean_selected is not None
        assert stats.sem_selected is None


class TestBuildIccsFromSnapshot:
    """Tests for building an ICCS instance from a snapshot."""

    def test_uses_snapshot_event_parameters(self, loaded_session: Session) -> None:
        """Verifies that the ICCS built from a snapshot uses the snapshot's
        event parameters, not the live ones changed after the snapshot was taken.

        Args:
            loaded_session: The database session with data loaded.
        """
        from pandas import Timedelta

        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        original_window_pre = event.parameters.window_pre

        # Take a snapshot that captures the original window_pre
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        # Shrink window_pre in the live DB after the snapshot was taken
        event.parameters.window_pre = original_window_pre - Timedelta(seconds=1)
        loaded_session.add(event.parameters)
        loaded_session.commit()
        loaded_session.refresh(event)
        assert event.parameters.window_pre != original_window_pre

        # Build ICCS from snapshot — must use the original value, not the live one
        bound = build_iccs_from_snapshot(loaded_session, snapshot.id)
        assert bound.iccs.window_pre == original_window_pre

    def test_uses_snapshot_seismogram_parameters(self, loaded_session: Session) -> None:
        """Verifies that the ICCS built from a snapshot uses the per-seismogram
        parameters captured at snapshot time, not any changes made afterwards.

        Args:
            loaded_session: The database session with data loaded.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        seis = event.seismograms[0]
        original_select = seis.parameters.select

        # Take a snapshot that captures the original select flag
        create_snapshot(loaded_session, event)
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()

        # Toggle select in the live DB after the snapshot was taken
        seis.parameters.select = not original_select
        loaded_session.add(seis.parameters)
        loaded_session.commit()
        loaded_session.refresh(event)

        # Build ICCS from snapshot — must use the original select flag
        bound = build_iccs_from_snapshot(loaded_session, snapshot.id)
        snapshot_seis = next(
            s for s in bound.iccs.seismograms if s.extra["id"] == seis.id
        )
        assert snapshot_seis.select == original_select
