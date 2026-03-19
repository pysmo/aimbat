"""Integration tests for ICCS alignment and MCCC quality clearing."""

from sqlmodel import Session, select

from aimbat.core import (
    create_iccs_instance,
    run_iccs,
    run_mccc,
)
from aimbat.models import AimbatEvent, AimbatSeismogramQuality


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
