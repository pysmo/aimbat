"""Helpers for resolving and shortening AIMBAT record UUIDs."""

from bisect import bisect_left
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
_ID_POOL_KEY = "aimbat_uuid_id_pools"


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

    The table's ids are fetched once per session and cached there, so calling
    this once per row (or once per cell) stays a single query - see
    `_id_pool` for what that caching does and does not guarantee.

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

    # Compare on the dash-free form throughout.
    target_clean = target_full.replace("-", "")

    pool = _id_pool(session, model_class, target_clean)
    if not _contains(pool, target_clean):
        raise ValueError(f"ID {target_full} not found in table {model_class.__name__}")

    length = min(
        max(min_length, _unique_prefix_length(pool, target_clean)), len(target_clean)
    )
    candidate = _dashed_prefix(target_full, length)
    logger.debug(f"Shortened {target_full} to: {candidate}")
    return candidate


def _id_pool[T: AimbatTypes](
    session: Session, model_class: type[T], target_clean: str
) -> list[str]:
    """Return every id in `model_class`'s table, dash-free and sorted.

    The pool is cached on `session`, so rendering a table of N rows costs one
    query per table rather than one per row (per cell, for the CLI's column
    formatters).

    A session that writes between two shortenings can therefore hold a stale
    pool. `target_clean` being absent forces a refetch, which covers a row
    this session has just added; a row added by another writer can still leave
    the returned prefix one character shorter than it needs to be, which is
    cosmetic and gone on the next session.
    """
    pools: dict[type[T], list[str]] = session.info.setdefault(_ID_POOL_KEY, {})
    pool = pools.get(model_class)
    if pool is None or not _contains(pool, target_clean):
        pool = sorted(
            str(uid).replace("-", "")
            for uid in session.exec(select(model_class.id)).all()
        )
        pools[model_class] = pool
    return pool


def _contains(pool: list[str], target: str) -> bool:
    """Whether the sorted `pool` holds `target`."""
    index = bisect_left(pool, target)
    return index < len(pool) and pool[index] == target


def _unique_prefix_length(pool: list[str], target: str) -> int:
    """Length of the shortest prefix of `target` no other id in `pool` shares."""
    index = bisect_left(pool, target)
    # `pool` is sorted, so the ids sharing the longest prefix with `target` are
    # the ones either side of it - nothing further out can share more.
    neighbours = [pool[i] for i in (index - 1, index + 1) if 0 <= i < len(pool)]
    return (
        max((_common_prefix_length(target, other) for other in neighbours), default=0)
        + 1
    )


def _common_prefix_length(first: str, second: str) -> int:
    """Number of leading characters `first` and `second` have in common."""
    length = 0
    for char_first, char_second in zip(first, second):
        if char_first != char_second:
            break
        length += 1
    return length


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
