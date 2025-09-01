"""Processing of data for AIMBAT."""

from __future__ import annotations
from aimbat.lib.event import get_active_event
from typing import TYPE_CHECKING
from pysmo.tools.iccs import ICCS, plotstack as _plotstack, stack_pick as _stack_pick

if TYPE_CHECKING:
    from sqlmodel import Session


def _create_iccs_instance(session: Session) -> ICCS:
    active_event = get_active_event(session)
    return ICCS(
        seismograms=active_event.seismograms,
        window_pre=active_event.parameters.window_pre,
        window_post=active_event.parameters.window_post,
    )


def plot_stack(session: Session) -> None:
    iccs = _create_iccs_instance(session)
    _plotstack(iccs)


def run_iccs(session: Session) -> None:
    iccs = _create_iccs_instance(session)
    iccs()
    session.commit()


def stack_pick(session: Session) -> None:
    iccs = _create_iccs_instance(session)
    _stack_pick(iccs)
    session.commit()
