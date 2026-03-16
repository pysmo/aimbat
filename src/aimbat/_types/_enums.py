from enum import StrEnum, auto

__all__ = ["EventParameter", "SeismogramParameter"]


class EventParameter(StrEnum):
    """[`AimbatEvent`][aimbat.models.AimbatEvent] enum for CLI arg typing."""

    COMPLETED = auto()
    MIN_CC = auto()
    WINDOW_PRE = auto()
    WINDOW_POST = auto()
    RAMP_WIDTH = auto()
    BANDPASS_APPLY = auto()
    BANDPASS_FMIN = auto()
    BANDPASS_FMAX = auto()
    MCCC_DAMP = auto()
    MCCC_MIN_CC = auto()


class SeismogramParameter(StrEnum):
    """[`AimbatSeismogramParameters`][aimbat.models.AimbatSeismogramParameters] enum for CLI arg typing."""

    SELECT = auto()
    FLIP = auto()
    T1 = auto()
