"""Unit tests for aimbat.utils.formatters."""

import numpy as np
import pandas as pd

from aimbat.utils.formatters import (
    fmt_bool,
    fmt_depth_km,
    fmt_flip,
    fmt_float,
    fmt_timedelta_sem,
)


class TestFmtDepthKm:
    """Tests for fmt_depth_km."""

    def test_formats_float(self) -> None:
        """Verifies a plain float is converted metres -> km."""
        assert fmt_depth_km(12345.0) == "12.3"

    def test_bool_is_not_treated_as_numeric(self) -> None:
        """Verifies a bool (int subclass) is not divided as a depth."""
        assert fmt_depth_km(True) == "True"
        assert fmt_depth_km(False) == "False"


class TestFmtBool:
    """Tests for fmt_bool."""

    def test_true(self) -> None:
        """Verifies Python True renders as a checkmark."""
        assert fmt_bool(True) == "✓"

    def test_false_and_none(self) -> None:
        """Verifies False/None render as an empty string."""
        assert fmt_bool(False) == ""
        assert fmt_bool(None) == ""

    def test_numpy_bool(self) -> None:
        """Verifies numpy.bool_ is recognised, not just Python bool."""
        assert fmt_bool(np.bool_(True)) == "✓"
        assert fmt_bool(np.bool_(False)) == ""


class TestFmtFlip:
    """Tests for fmt_flip."""

    def test_true_and_false(self) -> None:
        """Verifies True/False render as expected."""
        assert fmt_flip(True) == "↕"
        assert fmt_flip(False) == ""

    def test_numpy_bool(self) -> None:
        """Verifies numpy.bool_ is recognised, not just Python bool."""
        assert fmt_flip(np.bool_(True)) == "↕"
        assert fmt_flip(np.bool_(False)) == ""


class TestFmtFloat:
    """Tests for fmt_float."""

    def test_formats_float(self) -> None:
        """Verifies a plain float is formatted to 3 decimal places."""
        assert fmt_float(1.23456) == "1.235"

    def test_none(self) -> None:
        """Verifies None renders as the missing marker."""
        assert fmt_float(None) == " — "

    def test_nan(self) -> None:
        """Verifies NaN renders as the missing marker."""
        assert fmt_float(float("nan")) == " — "

    def test_nat(self) -> None:
        """Verifies pandas.NaT renders as the missing marker."""
        assert fmt_float(pd.NaT) == " — "

    def test_pd_na(self) -> None:
        """Verifies pandas.NA renders as the missing marker."""
        assert fmt_float(pd.NA) == " — "


class TestFmtTimedeltaSem:
    """Tests for fmt_timedelta_sem."""

    def test_mean_only(self) -> None:
        """Verifies a mean with no SEM formats without the +/- part."""
        assert fmt_timedelta_sem(pd.Timedelta(seconds=1.5), None) == "1.5000 s"

    def test_mean_and_sem(self) -> None:
        """Verifies mean and SEM both render."""
        result = fmt_timedelta_sem(pd.Timedelta(seconds=1.5), pd.Timedelta(seconds=0.1))
        assert result == "1.5000 ± 0.1000 s"

    def test_none(self) -> None:
        """Verifies a None mean renders as the missing marker."""
        assert fmt_timedelta_sem(None, None) == "—"

    def test_nat(self) -> None:
        """Verifies a NaT mean renders as the missing marker."""
        assert fmt_timedelta_sem(pd.NaT, None) == "—"  # type: ignore[arg-type]
