import math
from collections.abc import Callable
from typing import Any

from pandas import NaT, Timedelta, to_datetime

__all__ = [
    "Formatter",
    "fmt_bool",
    "fmt_depth_km",
    "fmt_flip",
    "fmt_float",
    "fmt_timedelta",
    "fmt_timestamp",
]

_MISSING_MARKER = " — "

type Formatter[T] = Callable[[T], str]


def fmt_depth_km(val: int | float | object) -> str:
    """Format a depth value in metres as kilometres with one decimal place."""
    if isinstance(val, (int, float)):
        return f"{val / 1000:.1f}"
    return str(val)


def fmt_bool(val: bool | object) -> str:
    """Format a boolean as `✓` (True) or empty string (False/None)."""
    return "✓" if val is True else ""


def fmt_float(val: float | object) -> str:
    """Format a float to 3 decimal places, or ` — ` for None/NaN."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return _MISSING_MARKER
    if isinstance(val, float):
        return f"{val:.3f}"
    return str(val)


def fmt_timestamp(val: Any) -> str:
    """Format a timestamp as `YYYY-MM-DD HH:MM:SS`, or ` — ` for missing values."""
    if isinstance(val, str) and val.strip():
        try:
            val = to_datetime(val)
        except (ValueError, TypeError):
            return str(val)
    if val is None or val is NaT or val == "":
        return _MISSING_MARKER
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)


def fmt_timedelta(val: Timedelta | object) -> str:
    """Format a Timedelta as total seconds to 5 decimal places, or ` — ` for None."""
    if val is None:
        return _MISSING_MARKER
    if isinstance(val, Timedelta):
        return f"{val.total_seconds():.5f} s"
    return str(val)


def fmt_flip(val: bool | object) -> str:
    """Format a boolean flip flag as `↕` (True) or empty string (False)."""
    if isinstance(val, bool):
        return "↕" if val else ""
    return str(val)
