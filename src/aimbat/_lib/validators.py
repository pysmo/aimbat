from pandas import Timedelta


def must_be_negative_pd_timedelta(v: Timedelta) -> Timedelta:
    """Validator to ensure a Timedelta is negative."""
    if v.total_seconds() >= 0:
        raise ValueError(f"Duration must be negative, got {v}")
    return v


def must_be_positive_pd_timedelta(v: Timedelta) -> Timedelta:
    """Validator to ensure a Timedelta is positive."""
    if v.total_seconds() <= 0:
        raise ValueError(f"Duration must be positive, got {v}")
    return v
