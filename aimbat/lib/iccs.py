"""Processing of data for AIMBAT."""

from __future__ import annotations
from aimbat.lib.common import logger
from aimbat.lib.defaults import get_default
from aimbat.lib.event import get_active_event
from aimbat.lib.typing import ProjectDefault
from pysmo.tools.iccs import (
    ICCS,
    plot_seismograms as _plot_seismograms,
    plot_stack as _plot_stack,
    update_min_ccnorm as _update_min_ccnorm,
    update_pick as _update_pick,
    update_timewindow as _update_timewindow,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlmodel import Session


def create_iccs_instance(session: Session) -> ICCS:
    """Create an ICCS instance for the active event.

    Parameters:
        session: Database session.

    Returns:
        ICCS instance.
    """

    logger.info("Creating ICCS instance for active event.")

    active_event = get_active_event(session)

    return ICCS(
        seismograms=active_event.seismograms,
        window_pre=active_event.parameters.window_pre,
        window_post=active_event.parameters.window_post,
        plot_padding=get_default(session, ProjectDefault.TIME_WINDOW_PADDING),
    )


def run_iccs(session: Session, iccs: ICCS, autoflip: bool, autoselect: bool) -> None:
    """Run ICCS algorithm.

    Parameters:
        session: Database session.
        iccs: ICCS instance.
        autoflip: Whether to automatically flip seismograms.
        autoselect: Whether to automatically select seismograms.
    """

    logger.info(f"Running ICCS with {autoflip=}, {autoselect=}.")

    results = iccs(autoflip=autoflip, autoselect=autoselect)
    logger.info(f"ICCS {results = }")
    session.commit()


def plot_stack(iccs: ICCS, padded: bool) -> None:
    """Plot the ICCS stack.

    Parameters:
        iccs: ICCS instance.
        padded: Whether to pad the stack.
    """

    logger.info("Plotting ICCS stack for active event.")
    _plot_stack(iccs, padded)


def plot_seismograms(iccs: ICCS, padded: bool) -> None:
    """Plot the ICCS seismograms.

    Parameters:
        iccs: ICCS instance.
        padded: Whether to pad the seismograms.
    """

    logger.info("Plotting ICCS seismograms for active event.")

    _plot_seismograms(iccs, padded)


def update_pick(
    session: Session, iccs: ICCS, padded: bool, use_seismogram_image: bool
) -> None:
    """Update the pick for the active event.

    Parameters:
        iccs: ICCS instance.
        padded: Whether to pad the seismograms.
        use_seismogram_image: Whether to use the seismogram image to update pick.
    """

    logger.info("Updating pick for active event.")

    _update_pick(iccs, padded, use_seismogram_image)
    session.commit()


def update_timewindow(
    session: Session, iccs: ICCS, padded: bool, use_seismogram_image: bool
) -> None:
    """Update the time window for the active event.

    Parameters:
        iccs: ICCS instance.
        padded: Whether to pad the seismograms.
        use_seismogram_image: Whether to use the seismogram image to update pick.
    """

    logger.info("Updating time window for active event.")

    logger.debug(f"Current {iccs.window_pre = }, {iccs.window_post = }.")
    _update_timewindow(iccs, padded, use_seismogram_image)
    logger.debug(f"Updated {iccs.window_pre = }, {iccs.window_post = }.")

    active_event = get_active_event(session)
    active_event.parameters.window_pre = iccs.window_pre
    active_event.parameters.window_post = iccs.window_post
    session.commit()


def update_min_ccnorm(session: Session, iccs: ICCS, padded: bool) -> None:
    """Update the minimum cross correlation coefficient for the active event.

    Parameters:
        iccs: ICCS instance.
        padded: Whether to pad the seismograms.
    """

    logger.info("Updating minimum cross correlation coefficient for active event.")

    logger.debug(f"Current {iccs.min_ccnorm = }.")
    _update_min_ccnorm(iccs, padded)
    logger.debug(f"Updated {iccs.min_ccnorm = }.")

    active_event = get_active_event(session)
    active_event.parameters.min_ccnorm = float(iccs.min_ccnorm)
    session.commit()
