"""Tests for aimbat._types._pydantic custom Pydantic types."""

import pytest
from pandas import NaT, Timedelta, Timestamp
from pydantic import BaseModel, TypeAdapter, ValidationError

from aimbat._types import (
    PydanticNegativeTimedelta,
    PydanticPositiveTimedelta,
    PydanticTimedelta,
    PydanticTimestamp,
)


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
        """Verifies that a timezone-aware pandas Timestamp is accepted."""
        ts = Timestamp("2020-01-01", tz="UTC")
        assert _TimestampModel(value=ts).value == ts

    def test_accepts_string(self) -> None:
        """Verifies that a valid, timezone-aware date string is accepted and converted."""
        m = _TimestampModel(value="2020-01-01T00:00:00Z")  # type: ignore[arg-type]
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

    def test_rejects_naive_timestamp(self) -> None:
        """Verifies that a naive pandas Timestamp is rejected."""
        with pytest.raises(ValidationError):
            _TimestampModel(value=Timestamp("2020-01-01"))

    def test_rejects_naive_string(self) -> None:
        """Verifies that a naive (no UTC offset) date string is rejected."""
        with pytest.raises(ValidationError):
            _TimestampModel(value="2020-01-01T00:00:00")  # type: ignore[arg-type]

    def test_rejects_nat(self) -> None:
        """Verifies that `pd.NaT` is rejected (a nullable field should use `None`)."""
        with pytest.raises(ValidationError):
            _TimestampModel(value=NaT)  # type: ignore[arg-type]


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

    def test_rejects_nat(self) -> None:
        """Verifies that `NaT` is rejected rather than passing every constraint."""
        with pytest.raises(ValidationError):
            _TimedeltaModel(value=NaT)  # type: ignore[arg-type]
        with pytest.raises(ValidationError):
            _TimedeltaModel(value="NaT")  # type: ignore[arg-type]

    def test_accepts_bare_number_as_seconds(self) -> None:
        """Verifies that a bare int/float is interpreted as a count of seconds."""
        assert _TimedeltaModel(value=30.2).value == Timedelta(  # type: ignore[arg-type]
            seconds=30.2
        )
        assert _TimedeltaModel(value=-20).value == Timedelta(seconds=-20)  # type: ignore[arg-type]

    def test_round_trips_through_serializer(self) -> None:
        """Verifies dump-then-validate reproduces the original Timedelta.

        Regression test: the serializer emits seconds, so the validator must
        interpret a bare number as seconds too, not nanoseconds.
        """
        ta: TypeAdapter[Timedelta] = TypeAdapter(PydanticTimedelta)
        original = Timedelta(seconds=30.2)
        dumped = ta.dump_python(original)
        assert ta.validate_python(dumped) == original


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

    def test_rejects_nat(self) -> None:
        """`NaT` must not slip past: `NaT >= 0` is False, so the negative check alone misses it."""

        class M(BaseModel):
            value: PydanticNegativeTimedelta

        with pytest.raises(ValidationError):
            M(value=NaT)  # type: ignore[arg-type]


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
