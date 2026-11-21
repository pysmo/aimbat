"""Integration tests for MCCC alignment in aimbat.core."""

import pytest
from pandas import Timedelta, Timestamp
from sqlmodel import Session, select

from pysmo.tools.iccs import ICCS, McccResult

from aimbat.core import (
    create_iccs_instance,
    run_mccc,
)
from aimbat.models import AimbatEvent, AimbatSeismogramQuality

from testsupport.project import first


class TestMccc:
    """Tests for Multi-Channel Cross-Correlation (MCCC) alignment."""

    def test_run_mccc_populates_quality_stats(self, loaded_session: Session) -> None:
        """Verifies that running MCCC populates quality metrics in the database."""
        event = first(loaded_session, AimbatEvent)

        # Ensure no MCCC stats initially
        if event.phases[0].quality:
            assert event.phases[0].quality.mccc_rmse is None

        # Run MCCC
        iccs_bound = create_iccs_instance(loaded_session, event.phases[0].id)
        run_mccc(
            loaded_session, event.phases[0].id, iccs_bound.iccs, all_seismograms=False
        )

        # Verify event-level stats
        loaded_session.refresh(event)
        assert event.phases[0].quality is not None
        assert event.phases[0].quality.mccc_rmse is not None
        assert isinstance(event.phases[0].quality.mccc_rmse, Timedelta)

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
            assert sq.mccc_refused is False

        # Seismograms outside the run have no MCCC values at all
        outside = loaded_session.exec(
            select(AimbatSeismogramQuality).where(
                AimbatSeismogramQuality.mccc_cc_mean == None  # noqa: E711
            )
        ).all()
        assert all(sq.mccc_refused is None for sq in outside)

    def test_run_mccc_all_seismograms(self, loaded_session: Session) -> None:
        """Verifies that MCCC can be run on all seismograms, including deselected ones."""
        event = first(loaded_session, AimbatEvent)

        # Deselect one seismogram
        seis_to_deselect = event.seismograms[0]
        seis_to_deselect.phase_rows[0].select = False
        loaded_session.add(seis_to_deselect.phase_rows[0])
        loaded_session.commit()
        loaded_session.refresh(event)

        # Run MCCC with all_seismograms=True
        iccs_bound = create_iccs_instance(loaded_session, event.phases[0].id)
        run_mccc(
            loaded_session, event.phases[0].id, iccs_bound.iccs, all_seismograms=True
        )

        # Verify deselected seismogram has MCCC stats
        loaded_session.refresh(seis_to_deselect)
        assert seis_to_deselect.phase_rows[0].quality is not None
        assert seis_to_deselect.phase_rows[0].quality.mccc_cc_mean is not None

    def test_run_mccc_selected_only(self, loaded_session: Session) -> None:
        """Verifies that MCCC only processes selected seismograms by default."""
        event = first(loaded_session, AimbatEvent)

        # Deselect one seismogram
        seis_to_deselect = event.seismograms[0]
        seis_to_deselect.phase_rows[0].select = False
        loaded_session.add(seis_to_deselect.phase_rows[0])
        loaded_session.commit()
        loaded_session.refresh(event)

        # Run MCCC with all_seismograms=False
        iccs_bound = create_iccs_instance(loaded_session, event.phases[0].id)
        run_mccc(
            loaded_session, event.phases[0].id, iccs_bound.iccs, all_seismograms=False
        )

        # Verify deselected seismogram has NO MCCC stats
        loaded_session.refresh(seis_to_deselect)
        if seis_to_deselect.phase_rows[0].quality:
            assert seis_to_deselect.phase_rows[0].quality.mccc_cc_mean is None


def _fake_mccc_result(
    indices: list[int],
    cc_means: list[float],
    cc_stds: list[float],
    refused: frozenset[int] = frozenset(),
) -> McccResult:
    """Build an `McccResult` for the given `ICCS.seismograms` indices."""
    n = len(indices)
    return McccResult(
        indices=indices,
        picks=[Timestamp("2010-02-27T06:40:00", tz="UTC")] * n,
        errors=[Timedelta(seconds=0.1)] * n,
        rmse=Timedelta(seconds=0.2),
        cc_means=cc_means,
        cc_stds=cc_stds,
        refused=refused,
    )


def _selected_indices(iccs: ICCS) -> list[int]:
    return [i for i, s in enumerate(iccs.seismograms) if s.select]


class TestWriteMcccQualityGuards:
    """`_write_mccc_quality` attribution, refusal handling and CC clamping."""

    def test_clamps_out_of_range_cc_values(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CC mean is clamped to [0, 1] and CC std to >= 0 before storage."""
        event = first(loaded_session, AimbatEvent)
        iccs = create_iccs_instance(loaded_session, event.phases[0].id).iccs
        indices = _selected_indices(iccs)
        n = len(indices)
        assert n >= 2

        cc_means = [1.5, -0.3] + [0.8] * (n - 2)
        cc_stds = [-0.1] + [0.05] * (n - 1)
        monkeypatch.setattr(
            ICCS,
            "run_mccc",
            lambda self, **kw: _fake_mccc_result(indices, cc_means, cc_stds),
        )
        run_mccc(loaded_session, event.phases[0].id, iccs, all_seismograms=False)

        loaded_session.expire_all()
        stored = loaded_session.exec(
            select(AimbatSeismogramQuality).where(
                AimbatSeismogramQuality.mccc_cc_mean != None  # noqa: E711
            )
        ).all()
        assert stored
        for sq in stored:
            assert sq.mccc_cc_mean is not None and 0.0 <= sq.mccc_cc_mean <= 1.0
            assert sq.mccc_cc_std is not None and sq.mccc_cc_std >= 0.0

    def test_metrics_follow_result_indices(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Metrics go to `ICCS.seismograms[indices[i]]`, not to position `i`."""
        event = first(loaded_session, AimbatEvent)
        iccs = create_iccs_instance(loaded_session, event.phases[0].id).iccs
        indices = _selected_indices(iccs)[::-1]
        n = len(indices)
        cc_means = [round(0.5 + i / (2 * n), 3) for i in range(n)]
        monkeypatch.setattr(
            ICCS,
            "run_mccc",
            lambda self, **kw: _fake_mccc_result(indices, cc_means, [0.05] * n),
        )
        run_mccc(loaded_session, event.phases[0].id, iccs, all_seismograms=False)

        loaded_session.expire_all()
        for index, cc_mean in zip(indices, cc_means, strict=True):
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality).where(
                    AimbatSeismogramQuality.seismogram_parameters_id
                    == iccs.seismograms[index].extra["row_id"]
                )
            ).one()
            assert sq.mccc_cc_mean == pytest.approx(cc_mean)

    def test_refused_seismogram_has_no_error(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A refused pick stores no error, but keeps its CC metrics."""
        event = first(loaded_session, AimbatEvent)
        iccs = create_iccs_instance(loaded_session, event.phases[0].id).iccs
        indices = _selected_indices(iccs)
        n = len(indices)
        refused = indices[0]
        monkeypatch.setattr(
            ICCS,
            "run_mccc",
            lambda self, **kw: _fake_mccc_result(
                indices, [0.8] * n, [0.05] * n, frozenset({refused})
            ),
        )
        run_mccc(loaded_session, event.phases[0].id, iccs, all_seismograms=False)

        loaded_session.expire_all()
        for index in indices:
            sq = loaded_session.exec(
                select(AimbatSeismogramQuality).where(
                    AimbatSeismogramQuality.seismogram_parameters_id
                    == iccs.seismograms[index].extra["row_id"]
                )
            ).one()
            assert sq.mccc_cc_mean == pytest.approx(0.8)
            assert sq.mccc_refused is (index == refused)
            if index == refused:
                assert sq.mccc_error is None
            else:
                assert sq.mccc_error == Timedelta(seconds=0.1)
