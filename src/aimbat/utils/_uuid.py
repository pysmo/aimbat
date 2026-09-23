"""Helpers for resolving and shortening AIMBAT record UUIDs."""

from uuid import UUID

from sqlalchemy import String, cast, func
from sqlmodel import Session, select

from aimbat import settings
from aimbat.logger import logger
from aimbat.models import AimbatTypes

__all__ = [
    "string_to_uuid",
    "uuid_shortener",
]

_LIKE_ESCAPE_CHAR = "\\"


def _escape_like(value: str) -> str:
    """Escape `%`, `_`, and the escape character itself for a SQL `LIKE` pattern."""
    return (
        value.replace(_LIKE_ESCAPE_CHAR, _LIKE_ESCAPE_CHAR * 2)
        .replace("%", f"{_LIKE_ESCAPE_CHAR}%")
        .replace("_", f"{_LIKE_ESCAPE_CHAR}_")
    )


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
        ValueError: If no record matches `id`, or more than one record does.
    """
    statement = select(aimbat_class.id).where(
        func.replace(cast(aimbat_class.id, String), "-", "").like(
            f"{_escape_like(id.replace('-', ''))}%", escape=_LIKE_ESCAPE_CHAR
        )
    )
    uuid_set = set(session.exec(statement).all())
    if len(uuid_set) == 1:
        resolved = uuid_set.pop()
        logger.debug(f"Resolved {id} to UUID: {resolved}")
        return resolved
    if len(uuid_set) == 0:
        raise ValueError(
            custom_error or f"Unable to find {aimbat_class.__name__} using id: {id}."
        )
    raise ValueError(f"Found more than one {aimbat_class.__name__} using id: {id}")


def uuid_shortener[T: AimbatTypes](
    session: Session,
    aimbat_obj: T | type[T],
    min_length: int | None = None,
    str_uuid: str | None = None,
) -> str:
    """Return the shortest unique prefix for a UUID, formatted with dashes.

    Args:
        session: An active SQLModel/SQLAlchemy session.
        aimbat_obj: Either an instance of a SQLModel or the SQLModel class itself.
        min_length: The starting character length for the shortened ID.
            Defaults to `Settings.min_id_length`.
        str_uuid: The full UUID string. Required only if `aimbat_obj` is a class.

    Returns:
        The shortest unique prefix string, including hyphens where applicable.

    Raises:
        ValueError: If `aimbat_obj` is a class and `str_uuid` is not
            provided, or if the resolved UUID has no matching record in the
            table.
    """

    if min_length is None:
        min_length = settings.min_id_length

    if isinstance(aimbat_obj, type):
        model_class = aimbat_obj
        if str_uuid is None:
            raise ValueError("str_uuid must be provided when aimbat_obj is a class.")
        target_full = str(UUID(str_uuid))
    else:
        model_class = type(aimbat_obj)
        target_full = str(aimbat_obj.id)

    target_clean = target_full.replace("-", "")
    prefix_clean = target_clean[:min_length]

    # select with a WHERE clause that removes dashes and compares the cleaned prefix
    statement = select(model_class.id).where(
        func.replace(cast(model_class.id, String), "-", "").like(
            f"{_escape_like(prefix_clean)}%", escape=_LIKE_ESCAPE_CHAR
        )
    )

    # Compare on the dash-free form throughout, to match prefix_clean above.
    results = session.exec(statement).all()
    relevant_pool = [str(uid).replace("-", "") for uid in results]

    if target_clean not in relevant_pool:
        raise ValueError(f"ID {target_full} not found in table {model_class.__name__}")

    current_length = min_length
    while current_length < len(target_clean):
        candidate_clean = target_clean[:current_length]
        matches = [u for u in relevant_pool if u.startswith(candidate_clean)]
        if len(matches) == 1:
            candidate = _dashed_prefix(target_full, current_length)
            logger.debug(f"Shortened {target_full} to: {candidate}")
            return candidate
        current_length += 1

    return target_full


def _dashed_prefix(full_dashed: str, clean_length: int) -> str:
    """Return the leading `clean_length` non-hyphen characters of `full_dashed`.

    Hyphens up to that point are preserved, matching how a full UUID string
    is conventionally shortened for display.
    """
    count = 0
    for i, ch in enumerate(full_dashed):
        if ch != "-":
            count += 1
        if count == clean_length:
            return full_dashed[: i + 1]
    return full_dashed
