"""Shared coercion of loosely-typed input into pandas time types.

Both the Pydantic validator (`_pydantic`) and the SQLAlchemy type decorator
(`_sqlalchemy`) route bare input through here so the two layers agree on what a
bare number means. `PydanticTimedelta` serialises to seconds via
`total_seconds()`, so a bare number must deserialise as **seconds** on both
sides - not as pandas' own default of nanoseconds. Keeping the rule in one
place stops the two layers drifting apart (a mismatch that is silently a
factor of 1e9).
"""

from typing import Any

from pandas import Timedelta

__all__ = ["coerce_to_timedelta"]


def coerce_to_timedelta(value: Any) -> Timedelta:
    """Coerce `value` to a `pandas.Timedelta`, treating bare numbers as seconds.

    A bare `int` / `float`, or a string that parses as a number, is read as a
    count of **seconds** - matching `PydanticTimedelta`'s `total_seconds()`
    serialisation, so a value survives a JSON round trip unchanged. A
    non-numeric string (`"1 days"`) and any other type fall back to
    `pandas.Timedelta`'s own parsing. An existing `Timedelta` is returned
    unchanged.
    """
    if isinstance(value, Timedelta):
        return value
    if isinstance(value, bool):
        raise TypeError(f"Cannot interpret bool {value!r} as a Timedelta")
    if isinstance(value, (int, float)):
        return Timedelta(seconds=float(value))
    if isinstance(value, str):
        try:
            return Timedelta(seconds=float(value))
        except ValueError:
            return Timedelta(value)
    return Timedelta(value)
