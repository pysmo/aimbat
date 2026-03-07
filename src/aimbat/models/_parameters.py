"""Base classes defining AIMBAT processing parameters."""

from typing import Self

from pydantic import model_validator
from sqlmodel import Field, SQLModel

from aimbat import settings
from aimbat._types import (
    PydanticNegativeTimedelta,
    PydanticPositiveTimedelta,
    PydanticTimestamp,
    SAPandasTimedelta,
    SAPandasTimestamp,
)

__all__ = [
    "AimbatEventParametersBase",
    "AimbatSeismogramParametersBase",
]


class AimbatEventParametersBase(SQLModel):
    """Base class defining event-level processing parameters for AIMBAT.

    This class serves as a base that is inherited by the actual classes that
    create the database tables. The attributes correspond exactly to the AIMBAT
    event parameters.
    """

    completed: bool = Field(
        default=False,
        title="Completed",
        description="Mark an event as completed.",
    )

    min_ccnorm: float = Field(
        ge=0.0,
        le=1.0,
        default_factory=lambda: settings.min_ccnorm,
        title="Min CC norm",
        description="Minimum cross-correlation used when automatically de-selecting seismograms.",
    )

    window_pre: PydanticNegativeTimedelta = Field(
        sa_type=SAPandasTimedelta,
        default_factory=lambda: settings.window_pre,
        title="Window pre",
        description="Pre-pick window length in seconds.",
    )

    window_post: PydanticPositiveTimedelta = Field(
        sa_type=SAPandasTimedelta,
        default_factory=lambda: settings.window_post,
        title="Window post",
        description="Post-pick window length in seconds.",
    )

    bandpass_apply: bool = Field(
        default_factory=lambda: settings.bandpass_apply,
        title="Bandpass apply",
        description="Whether to apply bandpass filter to seismograms.",
    )

    bandpass_fmin: float = Field(
        default_factory=lambda: settings.bandpass_fmin,
        ge=0,
        title="Bandpass f min",
        description="Minimum frequency for bandpass filter in Hz (ignored if `bandpass_apply` is False).",
    )

    bandpass_fmax: float = Field(
        default_factory=lambda: settings.bandpass_fmax,
        gt=0,
        title="Bandpass f max",
        description="Maximum frequency for bandpass filter in Hz (ignored if `bandpass_apply` is False).",
    )

    mccc_damp: float = Field(
        default_factory=lambda: settings.mccc_damp,
        ge=0,
        title="MCCC damp",
        description="Damping factor for MCCC algorithm.",
    )

    mccc_min_ccnorm: float = Field(
        default_factory=lambda: settings.mccc_min_ccnorm,
        ge=0,
        le=1,
        title="MCCC min CC norm",
        description="Minimum correlation coefficient required to include a pair in the MCCC inversion.",
    )

    @model_validator(mode="after")
    def check_freq_range(self) -> Self:
        """Validate that `bandpass_fmax` is strictly greater than `bandpass_fmin`."""
        if self.bandpass_fmax <= self.bandpass_fmin:
            raise ValueError("bandpass_fmax must be > bandpass_fmin")
        return self


class AimbatSeismogramParametersBase(SQLModel):
    """Base class defining seismogram-level processing parameters for AIMBAT."""

    flip: bool = Field(
        default=False,
        description="Whether or not the seismogram should be flipped.",
    )

    select: bool = Field(
        default=True,
        description="Whether or not this seismogram should be used for processing.",
    )

    t1: PydanticTimestamp | None = Field(
        default=None,
        sa_type=SAPandasTimestamp,
        description=(
            "Working pick. This pick serves as working as well as output pick."
            " It is changed by: 1. Picking the phase arrival in the stack,"
            " 2. Running ICCS, 3. Running MCCC."
        ),
    )
