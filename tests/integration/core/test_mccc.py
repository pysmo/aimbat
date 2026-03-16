"""Integration tests for MCCC alignment in aimbat.core."""

from pandas import Timedelta
from sqlmodel import Session, select

from aimbat.core import (
    create_iccs_instance,
    get_default_event,
    run_mccc,
)
from aimbat.models import AimbatSeismogramQuality


class TestMccc:
    """Tests for Multi-Channel Cross-Correlation (MCCC) alignment."""

    def test_run_mccc_populates_quality_stats(self, loaded_session: Session) -> None:
        """Verifies that running MCCC populates quality metrics in the database."""
        event = get_default_event(loaded_session)
        assert event is not None

        # Ensure no MCCC stats initially
        if event.quality:
            assert event.quality.mccc_rmse is None

        # Run MCCC
        iccs_bound = create_iccs_instance(loaded_session, event)
        run_mccc(loaded_session, event, iccs_bound.iccs, all_seismograms=False)

        # Verify event-level stats
        loaded_session.refresh(event)
        assert event.quality is not None
        assert event.quality.mccc_rmse is not None
        assert isinstance(event.quality.mccc_rmse, Timedelta)

        # Verify seismogram-level stats
        # At least some seismograms should have MCCC stats (those that were selected)
        seis_qualities = loaded_session.exec(
            select(AimbatSeismogramQuality).where(
                AimbatSeismogramQuality.mccc_cc_mean != None  # noqa: E711
            )
        ).all()
        assert len(seis_qualities) > 0
        for sq in seis_qualities:
            assert sq.mccc_cc_mean is not None
            assert sq.mccc_error is not None

    def test_run_mccc_all_seismograms(self, loaded_session: Session) -> None:
        """Verifies that MCCC can be run on all seismograms, including deselected ones."""
        event = get_default_event(loaded_session)
        assert event is not None

        # Deselect one seismogram
        seis_to_deselect = event.seismograms[0]
        seis_to_deselect.parameters.select = False
        loaded_session.add(seis_to_deselect.parameters)
        loaded_session.commit()
        loaded_session.refresh(event)

        # Run MCCC with all_seismograms=True
        iccs_bound = create_iccs_instance(loaded_session, event)
        run_mccc(loaded_session, event, iccs_bound.iccs, all_seismograms=True)

        # Verify deselected seismogram has MCCC stats
        loaded_session.refresh(seis_to_deselect)
        assert seis_to_deselect.quality is not None
        assert seis_to_deselect.quality.mccc_cc_mean is not None

    def test_run_mccc_selected_only(self, loaded_session: Session) -> None:
        """Verifies that MCCC only processes selected seismograms by default."""
        event = get_default_event(loaded_session)
        assert event is not None

        # Deselect one seismogram
        seis_to_deselect = event.seismograms[0]
        seis_to_deselect.parameters.select = False
        loaded_session.add(seis_to_deselect.parameters)
        loaded_session.commit()
        loaded_session.refresh(event)

        # Run MCCC with all_seismograms=False
        iccs_bound = create_iccs_instance(loaded_session, event)
        run_mccc(loaded_session, event, iccs_bound.iccs, all_seismograms=False)

        # Verify deselected seismogram has NO MCCC stats
        loaded_session.refresh(seis_to_deselect)
        if seis_to_deselect.quality:
            assert seis_to_deselect.quality.mccc_cc_mean is None
