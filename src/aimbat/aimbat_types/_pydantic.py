from aimbat._lib.validators import (
    must_be_negative_pd_timedelta,
    must_be_positive_pd_timedelta,
)
from typing import Annotated, Callable, Any, cast, ClassVar
from pydantic import AfterValidator
from pydantic_core.core_schema import CoreSchema, no_info_plain_validator_function
from pandas import Timestamp, Timedelta

__all__ = [
    "PydanticTimestamp",
    "PydanticTimedelta",
    "PydanticNegativeTimedelta",
    "PydanticPositiveTimedelta",
]


class _PandasBaseAnnotation[T: Timestamp | Timedelta]:
    """Base class to provide Pydantic core schema for Pandas types."""

    target_type: ClassVar[type[Timestamp] | type[Timedelta]]

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: Callable[[Any], CoreSchema]
    ) -> CoreSchema:
        # Define how to validate the input (from string, datetime, or object)
        def validate(value: Any) -> T:
            if isinstance(value, cls.target_type):
                return value
            try:
                result = cls.target_type(value)
                return cast(T, result)
            except Exception as e:
                raise ValueError(f"Could not parse {cls.target_type.__name__}: {e}")

        return no_info_plain_validator_function(validate)


class _AnnotatedTimestamp(_PandasBaseAnnotation):
    target_type = Timestamp


class _AnnotatedTimedelta(_PandasBaseAnnotation):
    target_type = Timedelta


type PydanticTimestamp = Annotated[Timestamp, _AnnotatedTimestamp]
type PydanticTimedelta = Annotated[Timedelta, _AnnotatedTimedelta]
type PydanticNegativeTimedelta = Annotated[
    PydanticTimedelta, AfterValidator(must_be_negative_pd_timedelta)
]
type PydanticPositiveTimedelta = Annotated[
    PydanticTimedelta, AfterValidator(must_be_positive_pd_timedelta)
]
