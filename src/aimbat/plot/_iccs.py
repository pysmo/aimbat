"""ICCS plotting and interactive parameter-adjustment functions for AIMBAT.

Wraps the plotting and interactive widget functions from `pysmo.tools.iccs`.
Where a widget lets a user change an alignment parameter (bandpass filter,
phase pick, time window, minimum CC threshold), the change is persisted to
the database once the interactive session ends.

The `update_*` functions take an event ID rather than a session, and open a
short-lived session of their own after the plot window closes. Nothing holds a
database connection for the minutes a user may spend in front of the window.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.engine import Engine
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

from aimbat.core._event import set_event_parameter, set_event_parameters
from aimbat.core._iccs import evict_iccs_cache_entry, write_back_seismograms
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
    "plot_matrix_image",
    "plot_stack",
    "update_bandpass",
    "update_min_cc",
    "update_pick",
    "update_timewindow",
]


@contextmanager
def _write_session(engine: Engine | None) -> Iterator[Session]:
    """Open a session for persisting what an interactive plot changed.

    Uses the project engine unless `engine` is given.
    """
    if engine is None:
        from aimbat.db import engine

    with Session(engine) as session:
        yield session


@contextmanager
def _evict_cached_iccs_on_failure(event_id: UUID) -> Iterator[None]:
    """Drop the event's cached ICCS instance if the enclosed write fails.

    The widgets mutate the process-cached ICCS instance in place while the
    user interacts with the plot, and the new values are only written to the
    database afterwards. A rejected write leaves those values on the cached
    instance without bumping `stack_modified`, so it never looks stale, and
    later callers in the same process (`aimbat shell`, the TUI) would keep
    being handed values the database refused.
    """
    try:
        yield
    except Exception:
        evict_iccs_cache_entry(event_id)
        raise


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


def update_bandpass(
    event_id: UUID,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    return_fig: bool,
    engine: Engine | None = None,
) -> tuple["Figure", "Axes", Any] | None:
    """Update the bandpass filter parameters for an event.

    Args:
        event_id: UUID of the event being updated.
        iccs: ICCS instance.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        use_matrix_image: If True, pick from the matrix image; otherwise pick from the stack plot.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.
        engine: Engine to persist the change with. Defaults to the project engine.

    Returns:
        A tuple of (Figure, Axes, widgets) if return_fig is True, otherwise None.
    """

    logger.info(f"Updating bandpass filter parameters for event {event_id}.")

    result = _update_bandpass(  # type: ignore[call-overload]
        iccs, context, all_seismograms, use_matrix_image, return_fig=return_fig
    )

    if not return_fig:
        logger.debug(
            f"Saving new bandpass filter parameters for event {event_id}: apply="
            + f"{iccs.bandpass_apply}, fmin={iccs.bandpass_fmin}, fmax="
            + f"{iccs.bandpass_fmax}, corners={iccs.corners}"
        )
        with _evict_cached_iccs_on_failure(event_id), _write_session(engine) as session:
            set_event_parameters(
                session,
                event_id,
                {
                    EventParameter.BANDPASS_APPLY: iccs.bandpass_apply,
                    EventParameter.BANDPASS_FMIN: iccs.bandpass_fmin,
                    EventParameter.BANDPASS_FMAX: iccs.bandpass_fmax,
                    EventParameter.CORNERS: iccs.corners,
                },
            )
        return None

    logger.debug(_RETURN_FIG_WARNING)
    return result


def update_pick(
    event_id: UUID,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    causal: bool,
    return_fig: bool,
    engine: Engine | None = None,
) -> tuple["Figure", "Axes", Any] | None:
    """Update the phase pick (t1) for an event.

    Args:
        event_id: UUID of the event being updated.
        iccs: ICCS instance.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        use_matrix_image: If True, pick from the matrix image; otherwise pick from the stack plot.
        causal: If True, use causal (single-pass) instead of zero-phase filtering.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.
        engine: Engine to persist the change with. Defaults to the project engine.

    Returns:
        A tuple of (Figure, Axes, widgets) if return_fig is True, otherwise None.
    """

    logger.info("Updating phase pick.")

    result = _update_pick(  # type: ignore[call-overload]
        iccs, context, all_seismograms, use_matrix_image, causal, return_fig=return_fig
    )

    if not return_fig:
        with _evict_cached_iccs_on_failure(event_id), _write_session(engine) as session:
            write_back_seismograms(session, iccs)
            session.commit()
        return None

    logger.debug(_RETURN_FIG_WARNING)
    return result


def update_timewindow(
    event_id: UUID,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    use_matrix_image: bool,
    causal: bool,
    return_fig: bool,
    engine: Engine | None = None,
) -> tuple["Figure", "Axes", Any] | None:
    """Update the cross-correlation time window for the given event.

    Args:
        event_id: UUID of the event being updated.
        iccs: ICCS instance.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        use_matrix_image: If True, pick from the matrix image; otherwise pick from the stack plot.
        causal: If True, use causal (single-pass) instead of zero-phase filtering.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.
        engine: Engine to persist the change with. Defaults to the project engine.

    Returns:
        A tuple of (Figure, Axes, widgets) if return_fig is True, otherwise None.
    """

    logger.info(f"Updating time window for event {event_id}.")

    result = _update_timewindow(  # type: ignore[call-overload]
        iccs, context, all_seismograms, use_matrix_image, causal, return_fig=return_fig
    )

    if not return_fig:
        logger.debug(
            f"Saving new time window for event {event_id}: pre={iccs.window_pre}, "
            + f"post={iccs.window_post}"
        )
        with _evict_cached_iccs_on_failure(event_id), _write_session(engine) as session:
            set_event_parameters(
                session,
                event_id,
                {
                    EventParameter.WINDOW_PRE: iccs.window_pre,
                    EventParameter.WINDOW_POST: iccs.window_post,
                },
            )
        return None

    logger.debug(_RETURN_FIG_WARNING)
    return result


def update_min_cc(
    event_id: UUID,
    iccs: ICCS,
    context: bool,
    all_seismograms: bool,
    causal: bool,
    return_fig: bool,
    engine: Engine | None = None,
) -> tuple["Figure", "Axes", Any] | None:
    """Update the minimum cross-correlation threshold for the given event.

    Args:
        event_id: UUID of the event being updated.
        iccs: ICCS instance.
        context: If True, plot waveforms with extra context around the taper window.
        all_seismograms: If True, include deselected seismograms in the plot.
        causal: If True, use causal (single-pass) instead of zero-phase filtering.
        return_fig: If True, return the figure, axes and widget objects instead of showing the plot.
        engine: Engine to persist the change with. Defaults to the project engine.

    Returns:
        A tuple of (Figure, Axes, widgets) if return_fig is True, otherwise None.
    """

    logger.info(f"Updating minimum cross-correlation threshold for event {event_id}.")

    result = _update_min_cc(  # type: ignore[call-overload]
        iccs, context, all_seismograms, causal, return_fig=return_fig
    )

    if not return_fig:
        logger.debug(
            f"Saving new minimum cross-correlation threshold for event {event_id}:"
            + f" {iccs.min_cc}"
        )
        with _evict_cached_iccs_on_failure(event_id), _write_session(engine) as session:
            set_event_parameter(
                session, event_id, EventParameter.MIN_CC, float(iccs.min_cc)
            )
        return None

    logger.debug(_RETURN_FIG_WARNING)
    return result
