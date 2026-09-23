"""Integration tests for ICCS alignment and MCCC quality clearing."""

import pytest
from pandas import Timestamp
from sqlalchemy import Engine
from sqlmodel import Session, select

from aimbat.core import (
    NoSeismogramsError,
    build_iccs_from_snapshot,
    cc_stats,
    clear_iccs_cache,
    create_iccs_instance,
    create_snapshot,
    delete_event,
    run_iccs,
    run_mccc,
)
from aimbat.models import (
    AimbatEvent,
    AimbatEventParameters,
    AimbatSeismogramQuality,
    AimbatSnapshot,
)


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


class TestCreateIccsInstanceNoSeismograms:
    """`create_iccs_instance` on an event with no seismograms."""

    @staticmethod
    def _empty_event(session: Session) -> AimbatEvent:
        event = AimbatEvent(
            time=Timestamp("2010-02-27T06:34:14", tz="UTC"),
            latitude=-36.12,
            longitude=-72.90,
            depth=22.9,
        )
        session.add(event)
        session.flush()
        session.add(AimbatEventParameters(event=event))
        session.flush()
        return event

    def test_raises_no_seismograms_error(self, loaded_session: Session) -> None:
        """A clean, catchable error rather than a failure deep inside pysmo."""
        event = self._empty_event(loaded_session)
        with pytest.raises(NoSeismogramsError):
            create_iccs_instance(loaded_session, event)

    def test_does_not_poison_the_cache(self, loaded_session: Session) -> None:
        """A failed build must not leave a half-initialised instance cached.

        Regression test: the broken instance used to be cached before the
        stats write that raises, so the next call returned it without
        re-raising and it blew up later on first stack access.
        """
        clear_iccs_cache()
        event = self._empty_event(loaded_session)

        with pytest.raises(NoSeismogramsError):
            create_iccs_instance(loaded_session, event)
        # Second call must raise again, not hand back a cached broken instance.
        with pytest.raises(NoSeismogramsError):
            create_iccs_instance(loaded_session, event)


class TestIccsCacheEviction:
    """Tests for the bounded, delete-event-evicted process-level ICCS cache."""

    def test_delete_event_evicts_cache_entry(self, loaded_session: Session) -> None:
        """A deleted event's cached BoundICCS must not linger in the process cache."""
        import aimbat.core._iccs as iccs_module

        clear_iccs_cache()
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        event_id = event.id

        create_iccs_instance(loaded_session, event)
        assert event_id in iccs_module._iccs_cache

        delete_event(loaded_session, event_id)

        assert event_id not in iccs_module._iccs_cache

    def test_cache_evicts_least_recently_used_once_full(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Once the cache is at its cap, the least-recently-used entry is dropped."""
        import aimbat.core._iccs as iccs_module

        clear_iccs_cache()
        monkeypatch.setattr(iccs_module, "_ICCS_CACHE_MAX_ENTRIES", 2)

        events = loaded_session.exec(select(AimbatEvent)).all()
        assert len(events) >= 3, "need at least 3 events to exercise eviction"
        first, second, third = events[0], events[1], events[2]

        create_iccs_instance(loaded_session, first)
        create_iccs_instance(loaded_session, second)
        assert first.id in iccs_module._iccs_cache
        assert second.id in iccs_module._iccs_cache

        create_iccs_instance(loaded_session, third)

        assert first.id not in iccs_module._iccs_cache, (
            "oldest entry should have been evicted once the cache was full"
        )
        assert second.id in iccs_module._iccs_cache
        assert third.id in iccs_module._iccs_cache

    def test_cache_hit_refreshes_recency(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-accessing a cached entry protects it from eviction as the LRU."""
        import aimbat.core._iccs as iccs_module

        clear_iccs_cache()
        monkeypatch.setattr(iccs_module, "_ICCS_CACHE_MAX_ENTRIES", 2)

        events = loaded_session.exec(select(AimbatEvent)).all()
        assert len(events) >= 3
        first, second, third = events[0], events[1], events[2]

        create_iccs_instance(loaded_session, first)
        create_iccs_instance(loaded_session, second)
        # Touch `first` again so `second` becomes the least-recently-used.
        create_iccs_instance(loaded_session, first)

        create_iccs_instance(loaded_session, third)

        assert first.id in iccs_module._iccs_cache
        assert second.id not in iccs_module._iccs_cache, (
            "re-accessing first should have made second the eviction target"
        )
        assert third.id in iccs_module._iccs_cache


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


class TestQualityWriteTransaction:
    """Tests that quality writes belong to the caller's transaction."""

    def test_iccs_cc_is_discarded_when_the_caller_rolls_back(
        self, loaded_engine: Engine
    ) -> None:
        """Building an ICCS instance writes CC values only if the caller commits.

        The write used to happen in a session of its own, so it survived a
        caller rollback and left the quality table describing a parameter
        state that was never persisted.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
        """
        clear_iccs_cache()
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            create_iccs_instance(session, event)
            assert any(
                q.iccs_cc is not None
                for q in session.exec(select(AimbatSeismogramQuality)).all()
            ), "the CC values should be visible inside the transaction"
            session.rollback()

        with Session(loaded_engine) as session:
            assert all(
                q.iccs_cc is None
                for q in session.exec(select(AimbatSeismogramQuality)).all()
            )

    def test_rollback_evicts_the_instance_so_the_next_build_rewrites_cc(
        self, loaded_engine: Engine
    ) -> None:
        """A rolled-back build is not served from the cache afterwards.

        A cache hit skips the CC write, so a surviving entry would leave
        `iccs_cc` empty indefinitely.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
        """
        from aimbat.core import _iccs as core_iccs

        clear_iccs_cache()
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            create_iccs_instance(session, event)
            assert event.id in core_iccs._iccs_cache
            session.rollback()
            assert event.id not in core_iccs._iccs_cache

            create_iccs_instance(session, event)
            session.commit()

        with Session(loaded_engine) as session:
            assert any(
                q.iccs_cc is not None
                for q in session.exec(select(AimbatSeismogramQuality)).all()
            )

    def test_commit_keeps_the_instance_cached(self, loaded_engine: Engine) -> None:
        """A commit leaves the cache entry alone, and a later rollback too.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
        """
        from aimbat.core import _iccs as core_iccs

        clear_iccs_cache()
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            create_iccs_instance(session, event)
            session.commit()
            session.rollback()
            assert event.id in core_iccs._iccs_cache

    def test_failed_mccc_quality_write_rolls_back_the_picks(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failure partway through `run_mccc` leaves nothing half-written.

        The three writes `run_mccc` makes used to be three commits across two
        sessions: failing on the last one left the picks committed, `iccs_cc`
        freshly repopulated and every MCCC column nulled by the triggers.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            monkeypatch: The pytest monkeypatch fixture.
        """
        from aimbat.core import _iccs as core_iccs

        clear_iccs_cache()
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            create_iccs_instance(session, event)
            session.commit()
            before = {
                q.seismogram_id: q.iccs_cc
                for q in session.exec(select(AimbatSeismogramQuality)).all()
            }
            picks_before = {s.id: s.parameters.t1 for s in event.seismograms}
        assert any(cc is not None for cc in before.values())

        def _boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("quality write failed")

        monkeypatch.setattr(core_iccs, "_write_mccc_quality", _boom)

        clear_iccs_cache()
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            iccs = create_iccs_instance(session, event).iccs
            with pytest.raises(RuntimeError, match="quality write failed"):
                run_mccc(session, event, iccs, all_seismograms=True)

        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            assert {s.id: s.parameters.t1 for s in event.seismograms} == picks_before
            assert {
                q.seismogram_id: q.iccs_cc
                for q in session.exec(select(AimbatSeismogramQuality)).all()
            } == before
