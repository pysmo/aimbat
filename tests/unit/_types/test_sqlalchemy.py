from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest
from sqlalchemy.engine import Dialect

from aimbat._types import SAPandasTimedelta, SAPandasTimestamp


@pytest.fixture
def mock_dialect() -> Dialect:
    """Fixture for a mock SQLAlchemy dialect."""
    return MagicMock(spec=Dialect)


class TestSAPandasTimestamp:
    """Tests for the SAPandasTimestamp custom SQLAlchemy type."""

    @pytest.fixture
    def sa_timestamp(self) -> SAPandasTimestamp:
        """Fixture providing an instance of SAPandasTimestamp."""
        return SAPandasTimestamp()

    def test_process_bind_param_none(
        self, sa_timestamp: SAPandasTimestamp, mock_dialect: Dialect
    ) -> None:
        """Test that None is passed through unchanged."""
        assert sa_timestamp.process_bind_param(None, mock_dialect) is None

    def test_process_bind_param_naive_timestamp(
        self, sa_timestamp: SAPandasTimestamp, mock_dialect: Dialect
    ) -> None:
        """Test that a naive pandas Timestamp is converted to a UTC datetime."""
        ts_naive = pd.Timestamp("2023-01-01 12:00:00")
        result = sa_timestamp.process_bind_param(ts_naive, mock_dialect)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        assert result.year == 2023
        assert result.hour == 12

    def test_process_bind_param_aware_timestamp(
        self, sa_timestamp: SAPandasTimestamp, mock_dialect: Dialect
    ) -> None:
        """Test that a timezone-aware pandas Timestamp is converted to UTC."""
        # Create a non-UTC timestamp
        ts_ny = pd.Timestamp("2023-01-01 12:00:00").tz_localize("America/New_York")
        result = sa_timestamp.process_bind_param(ts_ny, mock_dialect)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        # 12:00 NY is 17:00 UTC
        assert result.hour == 17

    def test_process_bind_param_converts_other_types(
        self, sa_timestamp: SAPandasTimestamp, mock_dialect: Dialect
    ) -> None:
        """Test that other datetime types are also converted correctly."""
        dt = datetime(2023, 1, 1, 12, 0, 0)
        result = sa_timestamp.process_bind_param(dt, mock_dialect)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_process_bind_param_truncates_nanoseconds(
        self, sa_timestamp: SAPandasTimestamp, mock_dialect: Dialect
    ) -> None:
        """Test that nanosecond precision is truncated to microseconds."""
        # DateTime in Python only supports microseconds, pandas supports nanoseconds
        ts_nano = pd.Timestamp("2023-01-01 12:00:00.123456789")
        result = sa_timestamp.process_bind_param(ts_nano, mock_dialect)
        assert result is not None
        # Should be truncated/floored to microseconds
        assert result.microsecond == 123456
        # Ensure it didn't round up or do something unexpected with the extra precision
        assert result.second == 0

    def test_process_result_value_none(
        self, sa_timestamp: SAPandasTimestamp, mock_dialect: Dialect
    ) -> None:
        """Test that None result is passed through unchanged."""
        assert sa_timestamp.process_result_value(None, mock_dialect) is None

    def test_process_result_value_naive_datetime(
        self, sa_timestamp: SAPandasTimestamp, mock_dialect: Dialect
    ) -> None:
        """Test that a naive datetime from DB is converted to a UTC pandas Timestamp."""
        # SQLAlchemy might return a naive datetime (implicit UTC or from DB)
        dt_naive = datetime(2023, 1, 1, 12, 0, 0)
        result = sa_timestamp.process_result_value(dt_naive, mock_dialect)
        assert isinstance(result, pd.Timestamp)
        assert result.tzinfo == timezone.utc
        assert result.year == 2023

    def test_process_result_value_aware_datetime(
        self, sa_timestamp: SAPandasTimestamp, mock_dialect: Dialect
    ) -> None:
        """Test that an aware datetime from DB is converted to a UTC pandas Timestamp."""
        dt_aware = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = sa_timestamp.process_result_value(dt_aware, mock_dialect)
        assert isinstance(result, pd.Timestamp)
        assert result.tzinfo == timezone.utc


class TestSAPandasTimedelta:
    """Tests for the SAPandasTimedelta custom SQLAlchemy type."""

    @pytest.fixture
    def sa_timedelta(self) -> SAPandasTimedelta:
        """Fixture providing an instance of SAPandasTimedelta."""
        return SAPandasTimedelta()

    def test_process_bind_param_none(
        self, sa_timedelta: SAPandasTimedelta, mock_dialect: Dialect
    ) -> None:
        """Test that None is passed through unchanged."""
        assert sa_timedelta.process_bind_param(None, mock_dialect) is None

    def test_process_bind_param_timedelta(
        self, sa_timedelta: SAPandasTimedelta, mock_dialect: Dialect
    ) -> None:
        """Test that a pandas Timedelta is converted to nanoseconds (int)."""
        td = pd.Timedelta(seconds=10)
        result = sa_timedelta.process_bind_param(td, mock_dialect)
        assert isinstance(result, int)
        assert result == 10 * 1_000_000_000  # nanoseconds

    def test_process_bind_param_duration_string(
        self, sa_timedelta: SAPandasTimedelta, mock_dialect: Dialect
    ) -> None:
        """Test that a pandas duration string is converted to nanoseconds."""
        result = sa_timedelta.process_bind_param("1 days", mock_dialect)
        assert isinstance(result, int)
        assert result == 86400 * 1_000_000_000

    @pytest.mark.parametrize("value", [10, -3, 0.05])
    def test_process_bind_param_bare_number_is_seconds(
        self,
        sa_timedelta: SAPandasTimedelta,
        mock_dialect: Dialect,
        value: float,
    ) -> None:
        """A bare number reaching the column is seconds, not nanoseconds.

        Table models skip Pydantic validation, so a bare number can reach
        `process_bind_param` directly; it must use the same seconds convention
        as `PydanticTimedelta` rather than pandas' nanosecond default.
        """
        result = sa_timedelta.process_bind_param(value, mock_dialect)
        assert result == int(pd.Timedelta(seconds=value).value)

    def test_process_bind_param_numeric_string_is_seconds(
        self, sa_timedelta: SAPandasTimedelta, mock_dialect: Dialect
    ) -> None:
        """A numeric string is seconds, matching `PydanticTimedelta`."""
        result = sa_timedelta.process_bind_param("15", mock_dialect)
        assert result == 15 * 1_000_000_000

    def test_bind_then_result_round_trips_bare_seconds(
        self, sa_timedelta: SAPandasTimedelta, mock_dialect: Dialect
    ) -> None:
        """bind(bare seconds) -> result() reproduces the same duration."""
        stored = sa_timedelta.process_bind_param(-12.5, mock_dialect)
        assert sa_timedelta.process_result_value(stored, mock_dialect) == pd.Timedelta(
            seconds=-12.5
        )

    def test_process_bind_param_rejects_nat_string(
        self, sa_timedelta: SAPandasTimedelta, mock_dialect: Dialect
    ) -> None:
        """The string "NaT" coerces to a Timedelta NaT; reject it rather than
        storing the iNaT sentinel integer - matching `PydanticTimedelta`.
        """
        with pytest.raises(ValueError, match="NaT"):
            sa_timedelta.process_bind_param("NaT", mock_dialect)

    def test_process_result_value_none(
        self, sa_timedelta: SAPandasTimedelta, mock_dialect: Dialect
    ) -> None:
        """Test that None result is passed through unchanged."""
        assert sa_timedelta.process_result_value(None, mock_dialect) is None

    def test_process_result_value_int(
        self, sa_timedelta: SAPandasTimedelta, mock_dialect: Dialect
    ) -> None:
        """Test that an integer (nanoseconds) from DB is converted to a pandas Timedelta."""
        ns_value = 5 * 1_000_000_000  # 5 seconds in ns
        result = sa_timedelta.process_result_value(ns_value, mock_dialect)
        assert isinstance(result, pd.Timedelta)
        assert result.total_seconds() == 5.0
