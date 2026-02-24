"""Tests for aimbat_types._pydantic custom Pydantic types."""

import pytest
from pydantic import BaseModel, ValidationError
from aimbat.aimbat_types import (
    PydanticTimestamp,
    PydanticTimedelta,
    PydanticNegativeTimedelta,
    PydanticPositiveTimedelta,
)
from pandas import Timestamp, Timedelta


class _TimestampModel(BaseModel):
    """Test model for PydanticTimestamp."""

    value: PydanticTimestamp


class _OptionalTimestampModel(BaseModel):
    """Test model for optional PydanticTimestamp."""

    value: PydanticTimestamp | None = None


class _TimedeltaModel(BaseModel):
    """Test model for PydanticTimedelta."""

    value: PydanticTimedelta


class TestPydanticTimestamp:
    """Tests for PydanticTimestamp custom type."""

    def test_accepts_timestamp(self) -> None:
        """Verifies that a pandas Timestamp is accepted."""
        ts = Timestamp("2020-01-01")
        assert _TimestampModel(value=ts).value == ts

    def test_accepts_string(self) -> None:
        """Verifies that a valid date string is accepted and converted to Timestamp."""
        m = _TimestampModel(value="2020-01-01")  # type: ignore[arg-type]
        assert isinstance(m.value, Timestamp)

    def test_rejects_none(self) -> None:
        """Verifies that None is rejected for a required field."""
        with pytest.raises(ValidationError):
            _TimestampModel(value=None)  # type: ignore[arg-type]

    def test_optional_accepts_none(self) -> None:
        """Verifies that None is accepted for an optional field."""
        assert _OptionalTimestampModel(value=None).value is None

    def test_rejects_invalid_string(self) -> None:
        """Verifies that an invalid date string raises ValidationError."""
        with pytest.raises(ValidationError):
            _TimestampModel(value="not-a-timestamp")  # type: ignore[arg-type]


class TestPydanticTimedelta:
    """Tests for PydanticTimedelta custom type."""

    def test_accepts_timedelta(self) -> None:
        """Verifies that a pandas Timedelta is accepted."""
        td = Timedelta(seconds=5)
        assert _TimedeltaModel(value=td).value == td

    def test_rejects_none(self) -> None:
        """Verifies that None is rejected."""
        with pytest.raises(ValidationError):
            _TimedeltaModel(value=None)  # type: ignore[arg-type]


class TestPydanticNegativeTimedelta:
    """Tests for PydanticNegativeTimedelta custom type."""

    def test_accepts_negative(self) -> None:
        """Verifies that a negative Timedelta is accepted."""

        class M(BaseModel):
            value: PydanticNegativeTimedelta

        assert M(value=Timedelta(seconds=-1)).value == Timedelta(seconds=-1)

    def test_rejects_positive(self) -> None:
        """Verifies that a positive Timedelta is rejected."""

        class M(BaseModel):
            value: PydanticNegativeTimedelta

        with pytest.raises(ValidationError):
            M(value=Timedelta(seconds=1))

    def test_rejects_zero(self) -> None:
        """Verifies that a zero Timedelta is rejected."""

        class M(BaseModel):
            value: PydanticNegativeTimedelta

        with pytest.raises(ValidationError):
            M(value=Timedelta(0))


class TestPydanticPositiveTimedelta:
    """Tests for PydanticPositiveTimedelta custom type."""

    def test_accepts_positive(self) -> None:
        """Verifies that a positive Timedelta is accepted."""

        class M(BaseModel):
            value: PydanticPositiveTimedelta

        assert M(value=Timedelta(seconds=1)).value == Timedelta(seconds=1)

    def test_rejects_negative(self) -> None:
        """Verifies that a negative Timedelta is rejected."""

        class M(BaseModel):
            value: PydanticPositiveTimedelta

        with pytest.raises(ValidationError):
            M(value=Timedelta(seconds=-1))

    def test_rejects_zero(self) -> None:
        """Verifies that a zero Timedelta is rejected."""

        class M(BaseModel):
            value: PydanticPositiveTimedelta

        with pytest.raises(ValidationError):
            M(value=Timedelta(0))
