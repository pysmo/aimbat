"""Tests for aimbat.types._coerce.

The Pydantic validator and the SQLAlchemy type decorator both route bare
input through `coerce_to_timedelta`; these tests pin the shared contract so
the two layers cannot drift into the 1e9 (seconds vs nanoseconds) mismatch.
"""

import pytest
from pandas import Timedelta

from aimbat.types._coerce import coerce_to_timedelta


class TestCoerceToTimedelta:
    """Contract for `coerce_to_timedelta`."""

    def test_timedelta_passes_through(self) -> None:
        """An existing Timedelta is returned unchanged."""
        td = Timedelta(seconds=30.2)
        assert coerce_to_timedelta(td) is td

    @pytest.mark.parametrize("value", [15, -20, 30.2, 0])
    def test_bare_number_is_seconds(self, value: float) -> None:
        """A bare int/float is a count of seconds, not nanoseconds."""
        assert coerce_to_timedelta(value) == Timedelta(seconds=value)

    @pytest.mark.parametrize("value", ["15", "-20", "30.2"])
    def test_numeric_string_is_seconds(self, value: str) -> None:
        """A numeric string is a count of seconds."""
        assert coerce_to_timedelta(value) == Timedelta(seconds=float(value))

    def test_duration_string_falls_back_to_pandas(self) -> None:
        """A non-numeric duration string uses pandas' own parsing."""
        assert coerce_to_timedelta("1 days") == Timedelta(days=1)

    def test_bool_is_rejected(self) -> None:
        """A bool is not a duration (and would otherwise coerce via int)."""
        with pytest.raises(TypeError):
            coerce_to_timedelta(True)


def test_matches_serialised_seconds_round_trip() -> None:
    """A Timedelta serialised to seconds coerces back to the same duration.

    This is the exact path that was off by 1e9: `PydanticTimedelta` dumps to
    `total_seconds()`, and that float must come back as the same duration on
    both the Pydantic and the SQLAlchemy side.
    """
    original = Timedelta(seconds=-12.5)
    assert coerce_to_timedelta(original.total_seconds()) == original
