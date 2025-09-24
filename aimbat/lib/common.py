"""Common functions for AIMBAT."""

from __future__ import annotations
from pysmo.tools.utils import uuid_shortener
from typing import TYPE_CHECKING
from sqlmodel import Session, select


if TYPE_CHECKING:
    from aimbat.lib.models import (
        AimbatEvent,
        AimbatSeismogram,
        AimbatSnapshot,
        AimbatStation,
    )
    from collections.abc import Sequence
    from uuid import UUID


__all__ = ["check_for_notebook"]


def string_to_uuid(
    session: Session,
    id: str,
    aimbat_class: type[AimbatEvent | AimbatSeismogram | AimbatSnapshot | AimbatStation],
) -> UUID:
    uuid_set = {
        u for u in session.exec(select(aimbat_class.id)).all() if str(u).startswith(id)
    }
    if len(uuid_set) == 1:
        return uuid_set.pop()
    if len(uuid_set) == 0:
        raise ValueError(f"Unable to determine {aimbat_class.__name__} from id: {id}")
    raise ValueError(f"Found more than one {aimbat_class.__name__} with id: {id}")


def reverse_uuid_shortener(
    uuids: Sequence[UUID], min_length: int = 2
) -> dict[UUID, str]:
    uuid_dict = uuid_shortener(uuids, min_length)
    return {v: k for k, v in uuid_dict.items()}


# NOTE: https://stackoverflow.com/questions/15411967/how-can-i-check-if-code-is-executed-in-the-ipython-notebook
def check_for_notebook() -> bool:
    """Check if we ware running inside a jupyter notebook."""
    from IPython.core.getipython import get_ipython

    try:
        shell = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False  # Probably standard Python interpreter
