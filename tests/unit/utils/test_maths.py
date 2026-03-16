"""Unit tests for aimbat.utils._maths."""

import pandas as pd
import pytest

from aimbat.utils._maths import mean_and_sem, mean_and_sem_timedelta


class TestMeanAndSem:
    """Tests for the get_stats_from_list function."""

    def test_basic_stats(self) -> None:
        """Verifies mean and SEM for a simple list of numbers."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        mean, sem = mean_and_sem(data)

        # Mean = (1+2+3+4+5)/5 = 3.0
        # SEM = std / sqrt(n)
        assert mean == pytest.approx(3.0)
        assert sem == pytest.approx(0.7071067811865476)  # 1.5811 / sqrt(5)

    def test_handles_none_values(self) -> None:
        """Verifies that None values are ignored in calculations."""
        data = [1.0, 2.0, None, 3.0]
        mean, sem = mean_and_sem(data)

        # Should be same as [1.0, 2.0, 3.0]
        # Mean = 2.0
        # SEM = 1.0 / sqrt(3) = 0.57735
        assert mean == pytest.approx(2.0)
        assert sem == pytest.approx(0.5773502691896257)

    def test_empty_list(self) -> None:
        """Verifies that an empty list returns (None, None)."""
        mean, sem = mean_and_sem([])
        assert mean is None
        assert sem is None

    def test_all_none(self) -> None:
        """Verifies that a list of only None returns (None, None)."""
        mean, sem = mean_and_sem([None, None])
        assert mean is None
        assert sem is None

    def test_single_value(self) -> None:
        """Verifies stats for a single value (SEM should be None/NaN)."""
        mean, sem = mean_and_sem([10.0])
        assert mean == 10.0
        # SEM requires at least 2 points
        assert sem is None

    def test_single_value_with_none(self) -> None:
        """Verifies stats for a single value plus Nones."""
        mean, sem = mean_and_sem([None, 10.0, None])
        assert mean == 10.0
        assert sem is None

    def test_integers(self) -> None:
        """Verifies that integer inputs are handled correctly."""
        data = [1, 2, 3]
        mean, sem = mean_and_sem(data)
        assert mean == pytest.approx(2.0)
        assert isinstance(mean, float)

    def test_caching_behaviour(self) -> None:
        """Verifies that the same input returns exactly the same result (caching)."""
        data = [1.1, 2.2, 3.3]
        res1 = mean_and_sem(data)
        res2 = mean_and_sem(data)
        assert res1 == res2
        # Since it's a tuple of floats, they should be identical
        assert res1[0] is res2[0] or res1[0] == res2[0]


class TestMeanAndSemTimedelta:
    """Tests for the mean_and_sem_timedelta function."""

    def test_basic_timedelta_stats(self) -> None:
        """Verifies mean and SEM for a simple list of timedeltas."""
        values = [
            pd.Timedelta(seconds=1),
            pd.Timedelta(seconds=2),
            pd.Timedelta(seconds=3),
            pd.Timedelta(seconds=4),
            pd.Timedelta(seconds=5),
        ]
        mean, sem = mean_and_sem_timedelta(values)

        assert mean == pd.Timedelta(seconds=3.0)
        assert sem == pytest.approx(pd.Timedelta(seconds=0.7071067811865476))

    def test_empty_list(self) -> None:
        """Verifies that an empty list returns (None, None)."""
        mean, sem = mean_and_sem_timedelta([])
        assert mean is None
        assert sem is None

    def test_single_value(self) -> None:
        """Verifies stats for a single timedelta (SEM should be None)."""
        values = [pd.Timedelta(seconds=10)]
        mean, sem = mean_and_sem_timedelta(values)

        assert mean == pd.Timedelta(seconds=10)
        assert sem is None

    def test_two_values(self) -> None:
        """Verifies stats for exactly two timedeltas."""
        values = [
            pd.Timedelta(seconds=1),
            pd.Timedelta(seconds=3),
        ]
        mean, sem = mean_and_sem_timedelta(values)

        assert mean == pd.Timedelta(seconds=2.0)
        assert sem is not None

    def test_milliseconds(self) -> None:
        """Verifies timedeltas with millisecond precision."""
        values = [
            pd.Timedelta(milliseconds=100),
            pd.Timedelta(milliseconds=200),
            pd.Timedelta(milliseconds=300),
        ]
        mean, sem = mean_and_sem_timedelta(values)

        assert mean == pd.Timedelta(milliseconds=200)
        assert sem is not None

    def test_negative_timedelta(self) -> None:
        """Verifies handling of negative timedeltas."""
        values = [
            pd.Timedelta(seconds=-2),
            pd.Timedelta(seconds=0),
            pd.Timedelta(seconds=2),
        ]
        mean, sem = mean_and_sem_timedelta(values)

        assert mean == pd.Timedelta(seconds=0)
        assert sem is not None

    def test_mixed_signs(self) -> None:
        """Verifies handling of mixed positive/negative timedeltas."""
        values = [
            pd.Timedelta(seconds=-3),
            pd.Timedelta(seconds=-1),
            pd.Timedelta(seconds=1),
            pd.Timedelta(seconds=3),
        ]
        mean, sem = mean_and_sem_timedelta(values)

        assert mean == pd.Timedelta(seconds=0)
        assert sem is not None
