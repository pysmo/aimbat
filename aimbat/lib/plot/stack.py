from __future__ import annotations
from aimbat.lib.processing import create_iccs_instance
from typing import TYPE_CHECKING
from pysmo.tools.iccs import plotstack as _plotstack

if TYPE_CHECKING:
    from sqlmodel import Session


def plot_stack(session: Session, padded: bool) -> None:
    iccs = create_iccs_instance(session)
    _plotstack(iccs, padded)
