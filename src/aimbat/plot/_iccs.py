"""ICCS plotting functions for AIMBAT."""

from typing import TYPE_CHECKING, Any

from sqlmodel import Session

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
    update_min_ccnorm as _update_min_ccnorm,
)
from pysmo.tools.iccs import (
    update_pick as _update_pick,
)
from pysmo.tools.iccs import (
    update_timewindow as _update_timewindow,
)

from aimbat.core._iccs import _write_back_seismograms
from aimbat.logger import logger
from aimbat.models import AimbatEvent

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

_RETURN_FIG_WARNING = (
    "Returning figure and axes objects instead of showing the plot. "
    "This is intended for testing purposes; in normal usage, return_fig should be False."
)

__all__ = [
    "plot_stack",
    "plot_matrix_image",
    "update_pick",
    "update_timewindow",
    "update_min_ccnorm",
]


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


def update_pick(
    session: Session,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    return_fig: bool,
) -> tuple["Figure", "Axes", Any] | None:
    """Update the phase pick (t1) for an event.

    Args:
        session: Database session.
        iccs: ICCS instance.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        use_matrix_image: If True, pick from the matrix image; otherwise pick from the stack plot.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.

    Returns:
        A tuple of (Figure, Axes, widgets) if return_fig is True, otherwise None.
    """

    logger.info("Updating phase pick.")

    result = _update_pick(  # type: ignore[call-overload]
        iccs, context, all_seismograms, use_matrix_image, return_fig=return_fig
    )

    if not return_fig:
        _write_back_seismograms(session, iccs)
        return None

    logger.warning(_RETURN_FIG_WARNING)
    return result


def update_timewindow(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    return_fig: bool,
) -> tuple["Figure", "Axes", Any] | None:
    """Update the cross-correlation time window for the given event.

    Args:
        session: Database session.
        event: AimbatEvent.
        iccs: ICCS instance.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        use_matrix_image: If True, pick from the matrix image; otherwise pick from the stack plot.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.

    Returns:
        A tuple of (Figure, Axes, widgets) if return_fig is True, otherwise None.
    """

    logger.info(f"Updating time window for event {event.id}.")

    result = _update_timewindow(  # type: ignore[call-overload]
        iccs, context, all_seismograms, use_matrix_image, return_fig=return_fig
    )

    if not return_fig:
        event.parameters.window_pre = iccs.window_pre
        event.parameters.window_post = iccs.window_post
        session.commit()
        return None

    logger.warning(_RETURN_FIG_WARNING)
    return result


def update_min_ccnorm(
    session: Session,
    event: AimbatEvent,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    return_fig: bool,
) -> tuple["Figure", "Axes", Any] | None:
    """Update the minimum cross-correlation threshold for the given event.

    Args:
        session: Database session.
        event: AimbatEvent.
        iccs: ICCS instance.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.

    Returns:
        A tuple of (Figure, Axes, widgets) if return_fig is True, otherwise None.
    """

    logger.info(f"Updating minimum cross-correlation threshold for event {event.id}.")

    result = _update_min_ccnorm(iccs, context, all_seismograms, return_fig=return_fig)  # type: ignore[call-overload]

    if not return_fig:
        event.parameters.min_ccnorm = float(iccs.min_ccnorm)
        session.commit()
        return None

    logger.warning(_RETURN_FIG_WARNING)
    return result
