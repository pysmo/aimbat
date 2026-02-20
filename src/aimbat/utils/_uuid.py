"""UUID functions for AIMBAT."""

from aimbat import settings
from aimbat.models import AimbatTypes
from pysmo.tools.utils import uuid_shortener as _uuid_shortener
from sqlmodel import Session, select
from uuid import UUID

__all__ = [
    "string_to_uuid",
    "uuid_shortener",
]


def string_to_uuid(
    session: Session,
    id: str,
    aimbat_class: type[AimbatTypes],
    custom_error: str | None = None,
) -> UUID:
    """Determine a UUID from a string containing the first few characters.

    Args:
        session: Database session.
        id: Input string to find UUID for.
        aimbat_class: Aimbat class to use to find UUID.
        custom_error: Overrides the default error message.

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
        raise ValueError(
            custom_error or f"Unable to find {aimbat_class.__name__} using id: {id}."
        )
    raise ValueError(f"Found more than one {aimbat_class.__name__} using id: {id}")


def uuid_shortener(
    session: Session,
    aimbat_obj: AimbatTypes,
    min_length: int = settings.min_id_length,
) -> str:
    uuids = session.exec(select(aimbat_obj.__class__.id)).all()
    uuid_dict = _uuid_shortener(uuids, min_length)
    reverse_uuid_dict = {v: k for k, v in uuid_dict.items()}
    return reverse_uuid_dict[aimbat_obj.id]
