from collections.abc import Sequence
from functools import lru_cache
from typing import Any

import pandas as pd

__all__ = ["mean_and_sem", "mean_and_sem_timedelta"]


def _narrow_pandas_type(val: Any) -> float | None:
    if isinstance(val, (int, float)) and pd.notna(val):
        return float(val)
    return None


@lru_cache(maxsize=1024)
def _mean_and_sem_tuple(
    data: tuple[float | None, ...],
) -> tuple[float | None, float | None]:

    series = pd.Series(data)

    return (
        _narrow_pandas_type(series.mean()),
        _narrow_pandas_type(series.sem()),
    )


def mean_and_sem(
    data: Sequence[float | None],
) -> tuple[float | None, float | None]:
    """Return the mean and standard error of the mean (SEM) for a list of numeric values, ignoring None values.

    Args:
        data: List of numeric values (float or int) or None.

    Returns:
        A tuple containing the mean and SEM of the input data, both as floats or None if not computable.
    """
    return _mean_and_sem_tuple(tuple(data))


def mean_and_sem_timedelta(
    values: Sequence[pd.Timedelta],
) -> tuple[pd.Timedelta | None, pd.Timedelta | None]:
    """Return (mean, sem) for a list of pd.Timedelta values.

    Args:
        values: List of pd.Timedelta values.

    Returns:
        `(None, None)` when empty. SEM is `None` for fewer than two values.
    """
    if not values:
        return None, None
    ns_vals = [float(td.value) for td in values]
    mean_ns, sem_ns = mean_and_sem(ns_vals)
    return (
        pd.Timedelta(int(mean_ns), unit="ns") if mean_ns is not None else None,
        pd.Timedelta(int(sem_ns), unit="ns") if sem_ns is not None else None,
    )
