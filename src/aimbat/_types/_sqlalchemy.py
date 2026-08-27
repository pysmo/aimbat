"""SQLAlchemy type decorators for storing pandas time types in the database.

Provides `SAPandasTimestamp` and `SAPandasTimedelta`, used as the `sa_type`
of SQLModel `Field()` definitions that hold `pandas.Timestamp` or
`pandas.Timedelta` values.
"""

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from pandas import Timedelta, Timestamp
from sqlalchemy.engine import Dialect
from sqlalchemy.types import BigInteger, DateTime, TypeDecorator

__all__ = [
    "SAPandasTimestamp",
    "SAPandasTimedelta",
]


class SAPandasTimestamp(TypeDecorator):
    """SQLAlchemy TypeDecorator for pandas.Timestamp.

    Ensures timezone-aware UTC storage in a DateTime column.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime | None:
        """Convert a value to a UTC-aware `datetime` for storage.

        Naive values are assumed to already be UTC; aware values are
        converted to UTC. Precision is truncated to microseconds, since
        `datetime` cannot represent nanoseconds.

        `PydanticTimestamp` validation is expected to have already rejected
        naive values before they reach this point; the naive-to-UTC handling
        here is a defensive fallback, not the primary validation point.

        Args:
            value: Value to store. `None` and pandas null values are passed
                through unchanged.
            dialect: The dialect in use for the current connection.

        Returns:
            A UTC-aware `datetime`, or `None` if `value` is null.
        """
        if pd.isnull(value):
            return None

        ts = value if isinstance(value, Timestamp) else Timestamp(value)

        # If naive (no TZ), localize to UTC. If aware, convert to UTC.
        if ts.tzinfo is None:
            ts = ts.tz_localize(timezone.utc)
        else:
            ts = ts.tz_convert(timezone.utc)

        # Truncate to microseconds: datetime lacks nanosecond precision.
        return ts.floor("us").to_pydatetime()

    def process_result_value(self, value: Any, dialect: Dialect) -> Timestamp | None:
        """Convert a stored value back to a UTC-aware `Timestamp`.

        Args:
            value: Value read from the database.
            dialect: The dialect in use for the current connection.

        Returns:
            A UTC-aware `Timestamp`, or `None` if `value` is `None`.
        """
        if value is None:
            return None

        ts = Timestamp(value)
        # Ensure the returned pandas object is always UTC aware
        if ts.tzinfo is None:
            return ts.tz_localize(timezone.utc)
        return ts.tz_convert(timezone.utc)


class SAPandasTimedelta(TypeDecorator):
    """SQLAlchemy TypeDecorator for pandas.Timedelta.

    Stores duration as an integer of nanoseconds for maximum precision.
    """

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> int | None:
        """Convert a value to an integer count of nanoseconds for storage.

        Args:
            value: Value to store. `None` and pandas null values are passed
                through unchanged.
            dialect: The dialect in use for the current connection.

        Returns:
            Duration in nanoseconds, or `None` if `value` is null.
        """
        if pd.isnull(value):
            return None

        td = value if isinstance(value, Timedelta) else Timedelta(value)
        # Explicit int cast for safety with some SQL drivers
        return int(td.value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Timedelta | None:
        """Convert a stored nanosecond count back to a `Timedelta`.

        Args:
            value: Value read from the database.
            dialect: The dialect in use for the current connection.

        Returns:
            The corresponding `Timedelta`, or `None` if `value` is `None`.
        """
        if value is None:
            return None
        # Construct pd.Timedelta from the nanosecond integer
        return Timedelta(value).as_unit("ns")
