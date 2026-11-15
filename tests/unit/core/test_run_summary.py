"""Tests for the user-facing summaries of ICCS and MCCC runs."""

import warnings

import numpy as np
import pytest
from pandas import Timedelta, Timestamp

from pysmo.tools.iccs import IccsResult, IccsStatus, McccResult

from aimbat.core import (
    ignore_run_summary_warnings,
    summarise_iccs_result,
    summarise_mccc_result,
)


def _iccs_result(
    status: IccsStatus = IccsStatus.converged,
    iterations: int = 3,
    refused: frozenset[int] = frozenset(),
    flipped: frozenset[int] = frozenset(),
    deselected: frozenset[int] = frozenset(),
    reselected: frozenset[int] = frozenset(),
    fallback: int | None = None,
) -> IccsResult:
    return IccsResult(
        convergence=np.zeros(iterations),
        status=status,
        refused=refused,
        flipped=flipped,
        deselected=deselected,
        reselected=reselected,
        fallback=fallback,
    )


def _mccc_result(n: int, refused: frozenset[int] = frozenset()) -> McccResult:
    return McccResult(
        indices=list(range(n)),
        picks=[Timestamp("2010-02-27T06:40:00", tz="UTC")] * n,
        errors=[Timedelta(seconds=0.1)] * n,
        rmse=Timedelta(seconds=0.2),
        cc_means=[0.8] * n,
        cc_stds=[0.05] * n,
        refused=refused,
    )


class TestSummariseIccsResult:
    def test_converged(self) -> None:
        summary = summarise_iccs_result(_iccs_result(), 5)
        assert summary.message == "ICCS converged after 3 iterations."
        assert not summary.warning

    def test_single_iteration(self) -> None:
        summary = summarise_iccs_result(_iccs_result(iterations=1), 5)
        assert summary.message == "ICCS converged after 1 iteration."

    def test_max_iter_is_a_warning(self) -> None:
        summary = summarise_iccs_result(_iccs_result(IccsStatus.max_iter), 5)
        assert summary.message == "ICCS did not converge after 3 iterations."
        assert summary.warning

    def test_nothing_applied_is_not_reported_as_converged(self) -> None:
        summary = summarise_iccs_result(
            _iccs_result(IccsStatus.nothing_applied, refused=frozenset(range(5))), 5
        )
        assert "converged" not in summary.message
        assert summary.message.startswith("ICCS moved no picks in 3 iterations")
        assert "Shorten the time window or the taper ramp." in summary.message
        assert summary.warning

    def test_refused_picks_are_counted(self) -> None:
        summary = summarise_iccs_result(_iccs_result(refused=frozenset({1, 3})), 5)
        assert (
            "In the final iteration, 2 of 5 picks could not be updated"
            in summary.message
        )
        assert summary.warning

    def test_selection_changes_are_listed_without_warning(self) -> None:
        summary = summarise_iccs_result(
            _iccs_result(
                flipped=frozenset({0}),
                deselected=frozenset({1, 2}),
                reselected=frozenset({3}),
            ),
            5,
        )
        assert summary.message.endswith(
            "Seismograms changed: 1 flipped, 2 deselected, 1 reselected."
        )
        assert not summary.warning

    def test_fallback_is_a_warning(self) -> None:
        summary = summarise_iccs_result(_iccs_result(fallback=2), 5)
        assert "best-correlating one was kept selected" in summary.message
        assert summary.warning


class TestSummariseMcccResult:
    def test_all_refined(self) -> None:
        summary = summarise_mccc_result(_mccc_result(4))
        assert summary.message == "MCCC refined 4 picks."
        assert not summary.warning

    @pytest.mark.parametrize(("n_refused", "verb"), [(1, "was"), (2, "were")])
    def test_refused_picks_are_counted(self, n_refused: int, verb: str) -> None:
        summary = summarise_mccc_result(
            _mccc_result(4, refused=frozenset(range(n_refused)))
        )
        assert summary.message.startswith(f"MCCC refined {4 - n_refused} of 4 picks.")
        assert f"{n_refused} {verb} left unchanged" in summary.message
        assert summary.warning


class TestIgnoreRunSummaryWarnings:
    @pytest.mark.parametrize(
        "message",
        [
            "ICCS refused the final-iteration shift of 1 of 3 seismogram(s)",
            "MCCC refused the shift of 1 of 3 pick(s)",
            "autoselect left no seismograms selected; keeping the best one",
        ],
    )
    def test_covered_warnings_are_ignored_even_as_errors(self, message: str) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            ignore_run_summary_warnings()
            warnings.warn(message, UserWarning)

    def test_other_warnings_still_apply(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            ignore_run_summary_warnings()
            with pytest.raises(UserWarning, match="something else"):
                warnings.warn("something else", UserWarning)
