"""ICCS related functions."""

from __future__ import annotations
from aimbat.lib.event import get_active_event
from pysmo.tools.iccs import ICCS
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlmodel import Session


def create_iccs_instance(session: Session) -> ICCS:
    active_event = get_active_event(session)
    return ICCS(
        seismograms=active_event.seismograms,
        window_pre=active_event.parameters.window_pre,
        window_post=active_event.parameters.window_post,
    )
