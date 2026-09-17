"""Formatters for displaying values in tables and panels."""

from collections.abc import Callable
from typing import Any, cast

import numpy as np
from pandas import NaT, Timedelta, isnull, to_datetime

__all__ = [
    "Formatter",
    "fmt_bool",
    "fmt_depth_km",
    "fmt_flip",
    "fmt_float",
    "fmt_float_sem",
    "fmt_timedelta",
    "fmt_timedelta_sem",
    "fmt_timestamp",
]

_MISSING_MARKER = " — "
_MISSING = "—"

type Formatter[T] = Callable[[T], str]


def fmt_depth_km(val: int | float | object) -> str:
    """Format a depth value in metres as kilometres with one decimal place."""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return f"{val / 1000:.1f}"
    return str(val)


def fmt_bool(val: bool | object) -> str:
    """Format a boolean as `✓` (True) or empty string (False/None)."""
    return "✓" if isinstance(val, (bool, np.bool_)) and val else ""


def fmt_float(val: float | object) -> str:
    """Format a float to 3 decimal places, or ` — ` for a null value (None/NaN/NaT/NA)."""
    if isnull(cast(Any, val)):
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
    if val is None or val is NaT or (isinstance(val, str) and val.strip() == ""):
        return _MISSING_MARKER
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)


def fmt_flip(val: bool | object) -> str:
    """Format a boolean flip flag as `↕` (True) or empty string (False)."""
    if isinstance(val, (bool, np.bool_)):
        return "↕" if val else ""
    return str(val)


def fmt_float_sem(v: float | None, sem: float | None, decimals: int = 4) -> str:
    """Format a float with an optional SEM as `value ± sem`, or `—` if `v` is `None`."""
    if v is None:
        return _MISSING
    if sem is not None:
        return f"{v:.{decimals}f} ± {sem:.{decimals}f}"
    return f"{v:.{decimals}f}"


def fmt_timedelta(td: Timedelta | None, decimals: int = 4) -> str:
    """Format a `Timedelta` as seconds, or `—` if `None`."""
    if td is None:
        return _MISSING
    return f"{td.total_seconds():.{decimals}f} s"


def fmt_timedelta_sem(
    mean: Timedelta | None, sem: Timedelta | None, decimals: int = 4
) -> str:
    """Format a `Timedelta` mean with an optional SEM as `mean ± sem` (in seconds).

    Returns `—` if `mean` is null (None/NaT/NA).
    """
    if isnull(cast(Any, mean)):
        return _MISSING
    assert mean is not None
    s = mean.total_seconds()
    if sem is not None:
        return f"{s:.{decimals}f} ± {sem.total_seconds():.{decimals}f} s"
    return f"{s:.{decimals}f} s"
