"""Base classes defining AIMBAT processing parameters."""

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Annotated, Self

from pydantic import model_validator
from sqlalchemy import Float
from sqlmodel import Field, SQLModel

from aimbat import settings
from aimbat.types import (
    PydanticNegativeTimedelta,
    PydanticNonNegativeFloat,
    PydanticPositiveTimedelta,
    PydanticTimestamp,
    SAPandasTimedelta,
    SAPandasTimestamp,
)

__all__ = [
    "AimbatEventParametersBase",
    "AimbatSeismogramParametersBase",
]


class Reach(StrEnum):
    """Whether a parameter is an input to a derived result, and for whom.

    This states which results a change makes out of date. The code that
    discards results may discard more than that.
    """

    NONE = auto()
    """Not an input. The result stays valid when the parameter changes."""

    EVENT = auto()
    """An input to the result for the whole event."""

    CONDITIONAL = auto()
    """As `EVENT` if the seismogram takes part in the result, otherwise an
    input to that seismogram's own values only. Taking part means being
    selected for the stack, and having been in the last run for MCCC."""


@dataclass(frozen=True)
class ParameterSpec:
    """What a processing parameter affects.

    Attach to a field with `Annotated[<type>, ParameterSpec(...)]`.
    """

    stack: Reach = Reach.NONE
    """Whether the parameter is an input to the ICCS stack, and so to `iccs_cc`."""

    mccc: Reach = Reach.NONE
    """Whether the parameter is an input to the MCCC results."""

    iccs_attribute: str | None = None
    """Name of the matching attribute on the ICCS instance or its seismograms."""

    bookkeeping: bool = False
    """Whether the parameter is a record for the user, not an input to processing."""

    def __post_init__(self) -> None:
        if self.stack is not Reach.NONE and self.iccs_attribute is None:
            raise ValueError(
                "A parameter that is an input to the stack needs an iccs_attribute."
            )
        if self.bookkeeping and (
            self.stack is not Reach.NONE
            or self.mccc is not Reach.NONE
            or self.iccs_attribute is not None
        ):
            raise ValueError("A bookkeeping parameter is not an input to processing.")


def _shapes_signal(iccs_attribute: str) -> ParameterSpec:
    """Spec of an event parameter that changes the signal ICCS and MCCC work on."""
    return ParameterSpec(
        stack=Reach.EVENT, mccc=Reach.EVENT, iccs_attribute=iccs_attribute
    )


_MCCC_ONLY = ParameterSpec(mccc=Reach.EVENT)


class AimbatEventParametersBase(SQLModel):
    """Base class defining event-level processing parameters for AIMBAT.

    This class serves as a base that is inherited by the actual classes that
    create the database tables. It covers the settings applied uniformly to
    all seismograms of an event: window bounds, taper ramp width, bandpass
    filter settings, the CC threshold for automatic de-selection, and MCCC
    settings.
    """

    completed: Annotated[bool, ParameterSpec(bookkeeping=True)] = Field(
        default=False,
        title="Completed",
        description="Mark an event as completed.",
    )

    ramp_width: Annotated[PydanticNonNegativeFloat, _shapes_signal("ramp_width")] = (
        Field(
            default_factory=lambda: settings.ramp_width,
            sa_type=Float,
            title="Ramp width",
            description=(
                "Width of taper ramp as a multiple of the window length. Values "
                + "greater than 1 are valid; the ramp extends outside the window."
            ),
        )
    )

    window_pre: Annotated[PydanticNegativeTimedelta, _shapes_signal("window_pre")] = (
        Field(
            sa_type=SAPandasTimedelta,
            default_factory=lambda: settings.window_pre,
            title="Window pre",
            description="Pre-pick window length in seconds.",
        )
    )

    window_post: Annotated[PydanticPositiveTimedelta, _shapes_signal("window_post")] = (
        Field(
            sa_type=SAPandasTimedelta,
            default_factory=lambda: settings.window_post,
            title="Window post",
            description="Post-pick window length in seconds.",
        )
    )

    bandpass_apply: Annotated[bool, _shapes_signal("bandpass_apply")] = Field(
        default_factory=lambda: settings.bandpass_apply,
        title="Bandpass apply",
        description="Whether to apply bandpass filter to seismograms.",
    )

    bandpass_fmin: Annotated[float, _shapes_signal("bandpass_fmin")] = Field(
        default_factory=lambda: settings.bandpass_fmin,
        ge=0,
        title="Bandpass f min",
        description=(
            "Minimum frequency for bandpass filter in Hz (ignored if "
            + "`bandpass_apply` is False)."
        ),
    )

    bandpass_fmax: Annotated[float, _shapes_signal("bandpass_fmax")] = Field(
        default_factory=lambda: settings.bandpass_fmax,
        gt=0,
        title="Bandpass f max",
        description=(
            "Maximum frequency for bandpass filter in Hz (ignored if "
            + "`bandpass_apply` is False)."
        ),
    )

    corners: Annotated[int, _shapes_signal("corners")] = Field(
        default_factory=lambda: settings.corners,
        gt=0,
        title="Corners",
        description=(
            "Number of corners (poles) for the bandpass filter (ignored if "
            + "`bandpass_apply` is False)."
        ),
        sa_column_kwargs={"server_default": "2"},
    )

    min_cc: Annotated[float, ParameterSpec(iccs_attribute="min_cc")] = Field(
        ge=0.0,
        le=1.0,
        default_factory=lambda: settings.min_cc,
        title="Min CC",
        description=(
            "Minimum cross-correlation used when automatically de-selecting "
            + "seismograms."
        ),
    )

    mccc_damp: Annotated[float, _MCCC_ONLY] = Field(
        default_factory=lambda: settings.mccc_damp,
        ge=0,
        title="MCCC damp",
        description="Damping factor for MCCC algorithm.",
    )

    mccc_min_cc: Annotated[float, _MCCC_ONLY] = Field(
        default_factory=lambda: settings.mccc_min_cc,
        ge=0,
        le=1,
        title="MCCC min CC",
        description=(
            "Minimum correlation coefficient required to include a pair in the "
            + "MCCC inversion."
        ),
    )

    @model_validator(mode="after")
    def check_freq_range(self) -> Self:
        """Validate that `bandpass_fmax` is strictly greater than `bandpass_fmin`."""
        if self.bandpass_fmax <= self.bandpass_fmin:
            raise ValueError(
                f"bandpass_fmax ({self.bandpass_fmax:g} Hz) must be greater than "
                + f"bandpass_fmin ({self.bandpass_fmin:g} Hz). Setting one bound at "
                + "a time, widen the band first: raise bandpass_fmax before "
                + "bandpass_fmin, lower bandpass_fmin before bandpass_fmax."
            )
        return self


class AimbatSeismogramParametersBase(SQLModel):
    """Base class defining seismogram-level processing parameters for AIMBAT.

    This class serves as a base that is inherited by the actual classes that
    create the database tables. It covers the per-seismogram `flip` and
    `select` flags and the working arrival-time pick `t1`.
    """

    flip: Annotated[
        bool,
        ParameterSpec(
            stack=Reach.CONDITIONAL, mccc=Reach.CONDITIONAL, iccs_attribute="flip"
        ),
    ] = Field(
        default=False,
        title="Flip",
        description="Whether or not the seismogram should be flipped.",
    )

    select: Annotated[
        bool, ParameterSpec(stack=Reach.EVENT, iccs_attribute="select")
    ] = Field(
        default=True,
        title="Select",
        description="Whether or not this seismogram should be used for processing.",
    )

    t1: Annotated[
        PydanticTimestamp | None,
        ParameterSpec(
            stack=Reach.CONDITIONAL,
            mccc=Reach.CONDITIONAL,
            iccs_attribute="refined_pick",
        ),
    ] = Field(
        default=None,
        sa_type=SAPandasTimestamp,
        title="T1",
        description=(
            "Working pick. This pick serves as working as well as output pick. It"
            + " is changed by: 1. Picking the phase arrival in the stack, 2. "
            + "Running ICCS, 3. Running MCCC."
        ),
    )


def _parameter_specs(model: type[SQLModel]) -> dict[str, ParameterSpec]:
    """Collect the `ParameterSpec` of every field on a parameter base model.

    Raises:
        TypeError: If a field has no `ParameterSpec`.
    """
    specs: dict[str, ParameterSpec] = {}
    for name, field in model.model_fields.items():
        found = [m for m in field.metadata if isinstance(m, ParameterSpec)]
        if len(found) != 1:
            raise TypeError(
                f"{model.__name__}.{name} needs exactly one ParameterSpec, "
                + f"found {len(found)}."
            )
        specs[name] = found[0]
    return specs


EVENT_PARAMETER_SPECS = _parameter_specs(AimbatEventParametersBase)
"""What each event parameter affects, keyed by field name."""

SEISMOGRAM_PARAMETER_SPECS = _parameter_specs(AimbatSeismogramParametersBase)
"""What each seismogram parameter affects, keyed by field name."""
