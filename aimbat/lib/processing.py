"""Processing of data for AIMBAT."""

from __future__ import annotations
from aimbat.lib.defaults import get_default
from aimbat.lib.event import get_active_event
from aimbat.lib.typing import ProjectDefault
from pysmo.tools.iccs import (
    ICCS,
    stack_pick as _stack_pick,
    stack_tw_pick as _stack_tw_pick,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlmodel import Session


def create_iccs_instance(session: Session) -> ICCS:
    active_event = get_active_event(session)
    return ICCS(
        seismograms=active_event.seismograms,
        window_pre=active_event.parameters.window_pre,
        window_post=active_event.parameters.window_post,
        plot_padding=get_default(session, ProjectDefault.TIME_WINDOW_PADDING),
    )


def run_iccs(session: Session) -> None:
    iccs = create_iccs_instance(session)
    iccs()
    session.commit()


def stack_pick(session: Session, padded: bool) -> None:
    iccs = create_iccs_instance(session)
    _stack_pick(iccs, padded)
    session.commit()


def stack_tw_pick(session: Session, padded: bool) -> None:
    iccs = create_iccs_instance(session)
    _stack_tw_pick(iccs, padded)
    active_event = get_active_event(session)
    active_event.parameters.window_pre = iccs.window_pre
    active_event.parameters.window_post = iccs.window_post
    session.commit()
