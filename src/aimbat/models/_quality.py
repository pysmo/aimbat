"""Base classes defining AIMBAT alignment quality metrics."""

from sqlmodel import Field, SQLModel

from aimbat._types import (
    PydanticPositiveTimedelta,
    SAPandasTimedelta,
)

__all__ = [
    "AimbatEventQualityBase",
    "AimbatSeismogramQualityBase",
]


class AimbatEventQualityBase(SQLModel):
    """Base class defining event-level quality metrics.

    Fields are `None` when the corresponding algorithm has not been run yet.
    """

    mccc_rmse: PydanticPositiveTimedelta | None = Field(
        default=None,
        sa_type=SAPandasTimedelta,
        title="MCCC RMSE",
        description="Root-mean-square error of the MCCC inversion fit across the whole array.",
    )


class AimbatSeismogramQualityBase(SQLModel):
    """Base class defining seismogram-level quality metrics.

    Fields are `None` when the corresponding algorithm has not been run for
    this seismogram.
    """

    iccs_cc: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        title="ICCS CC",
        description="Pearson cross-correlation coefficient of this seismogram with the ICCS stack.",
    )

    mccc_cc_mean: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        title="MCCC CC mean",
        description="Mean cross-correlation coefficient from the MCCC run (waveform quality).",
    )

    mccc_cc_std: float | None = Field(
        default=None,
        ge=0.0,
        title="MCCC CC std",
        description="Standard deviation of cross-correlation coefficients from the MCCC run (waveform consistency).",
    )

    mccc_error: PydanticPositiveTimedelta | None = Field(
        default=None,
        sa_type=SAPandasTimedelta,
        title="MCCC error",
        description="Timing precision (standard error from covariance matrix) from the MCCC run.",
    )
