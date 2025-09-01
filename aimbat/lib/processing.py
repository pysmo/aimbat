"""Processing of data for AIMBAT."""

from __future__ import annotations
from aimbat.lib.iccs import create_iccs_instance
from pysmo.tools.iccs import stack_pick as _stack_pick
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlmodel import Session


def run_iccs(session: Session) -> None:
    iccs = create_iccs_instance(session)
    iccs()
    session.commit()


def stack_pick(session: Session) -> None:
    iccs = create_iccs_instance(session)
    _stack_pick(iccs)
    session.commit()
