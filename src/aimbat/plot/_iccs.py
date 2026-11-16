"""ICCS plotting and interactive parameter-adjustment functions for AIMBAT.

Wraps the plotting and interactive widget functions from `pysmo.tools.iccs`.
Where a widget lets a user change an alignment parameter (bandpass filter,
phase pick, time window, minimum CC threshold), the `update_*` function
returns the new values once the plot window closes. Storing them is up to
the caller, through `aimbat.actions`.

The widgets apply the new values to the ICCS instance they are given as the
user interacts with the plot. Nothing in this module opens a database
session.
"""

from typing import TYPE_CHECKING, Any, Literal, overload
from uuid import UUID

from pandas import Timedelta, Timestamp

from pysmo.tools.iccs import (
    ICCS,
)
from pysmo.tools.iccs import (
    plot_matrix_image as _plot_matrix_image,
)
from pysmo.tools.iccs import (
    plot_stack as _plot_stack,
)
from pysmo.tools.iccs import (
    update_bandpass as _update_bandpass,
)
from pysmo.tools.iccs import (
    update_min_cc as _update_min_cc,
)
from pysmo.tools.iccs import (
    update_pick as _update_pick,
)
from pysmo.tools.iccs import (
    update_timewindow as _update_timewindow,
)

from aimbat.logger import logger
from aimbat.types import EventParameter

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

_RETURN_FIG_WARNING = (
    "Returning figure and axes objects instead of showing the plot. This "
    + "is intended for testing purposes; in normal usage, return_fig should"
    + " be False."
)

__all__ = [
    "EventParameterChanges",
    "plot_matrix_image",
    "plot_stack",
    "update_bandpass",
    "update_min_cc",
    "update_pick",
    "update_timewindow",
]

type EventParameterChanges = dict[EventParameter, bool | float | int | Timedelta]
"""New value for each event parameter set by an interactive tool."""

type _Figure = tuple["Figure", "Axes", Any]


def plot_stack(
    iccs: ICCS, context: bool, all_seismograms: bool, return_fig: bool
) -> tuple["Figure", "Axes"] | None:
    """Plot the ICCS stack.

    Args:
        iccs: ICCS instance.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        return_fig: If True, return the figure and axes objects instead of showing the plot.

    Returns:
        A tuple of (Figure, Axes) if return_fig is True, otherwise None.
    """

    logger.info("Plotting ICCS stack.")
    return _plot_stack(iccs, context, all_seismograms, return_fig=return_fig)  # type: ignore[call-overload]


def plot_matrix_image(
    iccs: ICCS, context: bool, all_seismograms: bool, return_fig: bool
) -> tuple["Figure", "Axes"] | None:
    """Plot the ICCS seismograms as a matrix image.

    The matrix is assembled from individual waveforms, with each row representing
    a different seismogram.

    Args:
        iccs: ICCS instance.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        return_fig: If True, return the figure and axes objects instead of showing the plot.

    Returns:
        A tuple of (Figure, Axes) if return_fig is True, otherwise None.
    """

    logger.info("Plotting matrix image.")

    return _plot_matrix_image(iccs, context, all_seismograms, return_fig=return_fig)  # type: ignore[call-overload]


@overload
def update_bandpass(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    return_fig: Literal[False],
) -> EventParameterChanges: ...


@overload
def update_bandpass(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    return_fig: Literal[True],
) -> _Figure: ...


def update_bandpass(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    return_fig: bool,
) -> EventParameterChanges | _Figure:
    """Adjust the bandpass filter interactively.

    Args:
        iccs: ICCS instance. The widget applies the new filter to it.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        use_matrix_image: If True, pick from the matrix image; otherwise pick from the stack plot.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.

    Returns:
        The new filter parameters once the window closes, or a tuple of
        (Figure, Axes, widgets) if `return_fig` is True.
    """

    logger.info("Updating bandpass filter parameters.")

    result = _update_bandpass(  # type: ignore[call-overload]
        iccs, context, all_seismograms, use_matrix_image, return_fig=return_fig
    )

    if return_fig:
        logger.debug(_RETURN_FIG_WARNING)
        return result

    return {
        EventParameter.BANDPASS_APPLY: iccs.bandpass_apply,
        EventParameter.BANDPASS_FMIN: iccs.bandpass_fmin,
        EventParameter.BANDPASS_FMAX: iccs.bandpass_fmax,
        EventParameter.CORNERS: iccs.corners,
    }


@overload
def update_pick(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    causal: bool,
    return_fig: Literal[False],
) -> dict[UUID, Timestamp]: ...


@overload
def update_pick(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    causal: bool,
    return_fig: Literal[True],
) -> _Figure: ...


def update_pick(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    causal: bool,
    return_fig: bool,
) -> dict[UUID, Timestamp] | _Figure:
    """Adjust the refined phase pick (`t1`) of every seismogram interactively.

    Args:
        iccs: ICCS instance. The widget applies the new picks to it.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        use_matrix_image: If True, pick from the matrix image; otherwise pick from the stack plot.
        causal: If True, use causal (single-pass) instead of zero-phase filtering.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.

    Returns:
        The refined pick of each seismogram once the window closes, keyed by
        seismogram ID, or a tuple of (Figure, Axes, widgets) if `return_fig`
        is True.
    """

    logger.info("Updating phase pick.")

    result = _update_pick(  # type: ignore[call-overload]
        iccs, context, all_seismograms, use_matrix_image, causal, return_fig=return_fig
    )

    if return_fig:
        logger.debug(_RETURN_FIG_WARNING)
        return result

    return {
        seis.extra["id"]: seis.refined_pick
        for seis in iccs.seismograms
        if seis.refined_pick is not None
    }


@overload
def update_timewindow(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    causal: bool,
    return_fig: Literal[False],
) -> EventParameterChanges: ...


@overload
def update_timewindow(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    causal: bool,
    return_fig: Literal[True],
) -> _Figure: ...


def update_timewindow(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    causal: bool,
    return_fig: bool,
) -> EventParameterChanges | _Figure:
    """Adjust the cross-correlation time window interactively.

    Args:
        iccs: ICCS instance. The widget applies the new window to it.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        use_matrix_image: If True, pick from the matrix image; otherwise pick from the stack plot.
        causal: If True, use causal (single-pass) instead of zero-phase filtering.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.

    Returns:
        The new window parameters once the window closes, or a tuple of
        (Figure, Axes, widgets) if `return_fig` is True.
    """

    logger.info("Updating time window.")

    result = _update_timewindow(  # type: ignore[call-overload]
        iccs, context, all_seismograms, use_matrix_image, causal, return_fig=return_fig
    )

    if return_fig:
        logger.debug(_RETURN_FIG_WARNING)
        return result

    return {
        EventParameter.WINDOW_PRE: iccs.window_pre,
        EventParameter.WINDOW_POST: iccs.window_post,
    }


@overload
def update_min_cc(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    causal: bool,
    return_fig: Literal[False],
) -> EventParameterChanges: ...


@overload
def update_min_cc(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    causal: bool,
    return_fig: Literal[True],
) -> _Figure: ...


def update_min_cc(
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    causal: bool,
    return_fig: bool,
) -> EventParameterChanges | _Figure:
    """Adjust the minimum cross-correlation threshold interactively.

    Args:
        iccs: ICCS instance. The widget applies the new threshold to it.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        causal: If True, use causal (single-pass) instead of zero-phase filtering.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.

    Returns:
        The new threshold once the window closes, or a tuple of
        (Figure, Axes, widgets) if `return_fig` is True.
    """

    logger.info("Updating minimum cross-correlation threshold.")

    result = _update_min_cc(  # type: ignore[call-overload]
        iccs, context, all_seismograms, causal, return_fig=return_fig
    )

    if return_fig:
        logger.debug(_RETURN_FIG_WARNING)
        return result

    return {EventParameter.MIN_CC: float(iccs.min_cc)}
