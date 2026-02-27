from typing import Any
from pandas import Timestamp, Timedelta
from datetime import datetime, timezone
from sqlalchemy.types import TypeDecorator, DateTime, BigInteger
from sqlalchemy.engine import Dialect

__all__ = [
    "SAPandasTimestamp",
    "SAPandasTimedelta",
]


class SAPandasTimestamp(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for pandas.Timestamp.
    Ensures timezone-aware UTC storage in a DateTime column.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
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
        if value is None:
            return None

        ts = Timestamp(value)
        # Ensure the returned pandas object is always UTC aware
        if ts.tzinfo is None:
            return ts.tz_localize(timezone.utc)
        return ts.tz_convert(timezone.utc)


class SAPandasTimedelta(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for pandas.Timedelta.
    Stores duration as an integer of nanoseconds for maximum precision.
    """

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> int | None:
        if value is None:
            return None

        td = value if isinstance(value, Timedelta) else Timedelta(value)
        # Explicit int cast for safety with some SQL drivers
        return int(td.value)

    def process_result_value(self, value: Any, dialect: Dialect) -> Timedelta | None:
        if value is None:
            return None
        # Construct pd.Timedelta from the nanosecond integer
        return Timedelta(value).as_unit("ns")
