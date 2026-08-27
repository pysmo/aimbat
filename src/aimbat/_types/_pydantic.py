"""Pydantic annotations for validating and serialising pandas time types.

Provides `PydanticTimestamp` and `PydanticTimedelta` — pandas-native
equivalents of Pydantic's own datetime/timedelta support — along with
`Timedelta` variants constrained to negative, positive, or non-negative
values, and a non-negative float constraint.
"""

from typing import Annotated, Any, Callable, ClassVar, cast

from pandas import Timedelta, Timestamp
from pydantic import AfterValidator, Field, PlainSerializer
from pydantic_core.core_schema import CoreSchema, no_info_plain_validator_function

__all__ = [
    "PydanticTimestamp",
    "PydanticTimedelta",
    "PydanticNegativeTimedelta",
    "PydanticPositiveTimedelta",
    "PydanticNonNegativeTimedelta",
    "PydanticNonNegativeFloat",
]


def _format_timedelta(td: Timedelta | None) -> float | None:
    if td is None:
        return None
    return td.total_seconds()


def _must_be_negative_pd_timedelta(v: Timedelta) -> Timedelta:
    """Validator to ensure a Timedelta is negative."""
    if v.total_seconds() >= 0:
        raise ValueError(f"Duration must be negative, got {v}")
    return v


def _must_be_positive_pd_timedelta(v: Timedelta) -> Timedelta:
    """Validator to ensure a Timedelta is positive."""
    if v.total_seconds() <= 0:
        raise ValueError(f"Duration must be positive, got {v}")
    return v


def _must_be_non_negative_pd_timedelta(v: Timedelta) -> Timedelta:
    """Validator to ensure a Timedelta is non-negative."""
    if v.total_seconds() < 0:
        raise ValueError(f"Duration must be non-negative, got {v}")
    return v


class _PandasBaseAnnotation[T: Timestamp | Timedelta]:
    """Base class to provide Pydantic core schema for Pandas types."""

    target_type: ClassVar[type[Timestamp] | type[Timedelta]]

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: Callable[[Any], CoreSchema]
    ) -> CoreSchema:
        # Define how to validate the input (from string, datetime, or object)
        def validate(value: Any) -> T:
            if value is None:
                raise ValueError(f"{cls.target_type.__name__} value cannot be None")
            if isinstance(value, cls.target_type):
                result = cast(T, value)
            else:
                try:
                    # Interpret bare numbers (and numeric strings) as seconds
                    # for Timedelta, matching the seconds-based serialisation.
                    if cls.target_type is Timedelta and isinstance(value, str):
                        try:
                            result = cast(T, Timedelta(seconds=float(value)))
                        except ValueError:
                            result = cast(T, cls.target_type(value))
                    elif (
                        cls.target_type is Timedelta
                        and isinstance(value, int | float)
                        and not isinstance(value, bool)
                    ):
                        result = cast(T, Timedelta(seconds=float(value)))
                    else:
                        result = cast(T, cls.target_type(value))
                except Exception as e:
                    raise ValueError(f"Could not parse {cls.target_type.__name__}: {e}")
            if cls.target_type is Timestamp and cast(Timestamp, result).tzinfo is None:
                raise ValueError(
                    f"Timestamp value must be timezone-aware (UTC), got naive "
                    f"value {result!r}"
                )
            return result

        return no_info_plain_validator_function(validate)


class _AnnotatedTimestamp(_PandasBaseAnnotation):
    """Pydantic core-schema provider for `pandas.Timestamp`."""

    target_type = Timestamp


class _AnnotatedTimedelta(_PandasBaseAnnotation):
    """Pydantic core-schema provider for `pandas.Timedelta`."""

    target_type = Timedelta


type PydanticTimestamp = Annotated[Timestamp, _AnnotatedTimestamp]
type PydanticTimedelta = Annotated[
    Timedelta,
    _AnnotatedTimedelta,
    PlainSerializer(_format_timedelta, return_type=float | None),
]
type PydanticNegativeTimedelta = Annotated[
    PydanticTimedelta, AfterValidator(_must_be_negative_pd_timedelta)
]
type PydanticPositiveTimedelta = Annotated[
    PydanticTimedelta, AfterValidator(_must_be_positive_pd_timedelta)
]
type PydanticNonNegativeTimedelta = Annotated[
    PydanticTimedelta, AfterValidator(_must_be_non_negative_pd_timedelta)
]
type PydanticNonNegativeFloat = Annotated[float, Field(ge=0.0)]
