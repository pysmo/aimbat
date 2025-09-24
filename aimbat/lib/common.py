"""Common functions for AIMBAT."""

from __future__ import annotations
from pysmo.tools.utils import uuid_shortener as _uuid_shortener
from sqlmodel import Session, select
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from aimbat.lib.models import AimbatTypes
    from uuid import UUID


def string_to_uuid(session: Session, id: str, aimbat_class: type[AimbatTypes]) -> UUID:
    """Determine a UUID from a string containing the first few characters.

    Parameters:
        session: Database session.
        id: Input string to find UUID for.
        aimbat_class: Aimbat class to use to find UUID.

    Returns:
        The full UUID.

    Raises:
        ValueError: If the UUID could not be determined.
    """
    uuid_set = {
        u for u in session.exec(select(aimbat_class.id)).all() if str(u).startswith(id)
    }
    if len(uuid_set) == 1:
        return uuid_set.pop()
    if len(uuid_set) == 0:
        raise ValueError(f"Unable to determine {aimbat_class.__name__} from id: {id}")
    raise ValueError(f"Found more than one {aimbat_class.__name__} with id: {id}")


def uuid_shortener(
    session: Session,
    aimbat_obj: AimbatTypes,
    min_length: int = 2,
) -> str:
    uuids = session.exec(select(aimbat_obj.__class__.id)).all()
    uuid_dict = _uuid_shortener(uuids, min_length)
    reverse_uuid_dict = {v: k for k, v in uuid_dict.items()}
    return reverse_uuid_dict[aimbat_obj.id]


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
