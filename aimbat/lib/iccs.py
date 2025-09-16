"""Processing of data for AIMBAT."""

from __future__ import annotations
from aimbat.lib.common import logger
from aimbat.lib.defaults import get_default
from aimbat.lib.event import get_active_event
from aimbat.lib.typing import ProjectDefault
from pysmo.tools.iccs import (
    ICCS,
    select_min_ccnorm as _select_min_ccnorm,
    stack_pick as _stack_pick,
    stack_timewindow as _stack_timewindow,
    plotstack as _plotstack,
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

    iccs(autoflip=autoflip, autoselect=autoselect)
    session.commit()


def plot_stack(iccs: ICCS, padded: bool) -> None:
    _plotstack(iccs, padded)


def stack_pick(session: Session, iccs: ICCS, padded: bool) -> None:
    _stack_pick(iccs, padded)
    session.commit()


def stack_timewindow(session: Session, iccs: ICCS, padded: bool) -> None:
    _ = _stack_timewindow(iccs, padded)
    active_event = get_active_event(session)
    active_event.parameters.window_pre = iccs.window_pre
    active_event.parameters.window_post = iccs.window_post
    session.commit()


def select_min_ccnorm(session: Session, iccs: ICCS, padded: bool) -> None:
    _ = _select_min_ccnorm(iccs, padded)
    active_event = get_active_event(session)
    active_event.parameters.min_ccnorm = float(iccs.min_ccnorm)
    session.commit()
