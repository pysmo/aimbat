"""UUID functions for AIMBAT."""

from aimbat.models import AimbatTypes
from sqlmodel import Session, select
from sqlalchemy import cast, String, func
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
    statement = select(aimbat_class.id).where(
        func.replace(cast(aimbat_class.id, String), "-", "").like(
            f"{id.replace('-', '')}%"
        )
    )
    uuid_set = set(session.exec(statement).all())
    if len(uuid_set) == 1:
        return uuid_set.pop()
    if len(uuid_set) == 0:
        raise ValueError(
            custom_error or f"Unable to find {aimbat_class.__name__} using id: {id}."
        )
    raise ValueError(f"Found more than one {aimbat_class.__name__} using id: {id}")


def uuid_shortener[T: AimbatTypes](
    session: Session,
    aimbat_obj: T | type[T],
    min_length: int = 2,
    str_uuid: str | None = None,
) -> str:
    """Calculates the shortest unique prefix for a UUID, returning with dashes.

    Args:
        session: An active SQLModel/SQLAlchemy session.
        aimbat_obj: Either an instance of a SQLModel or the SQLModel class itself.
        min_length: The starting character length for the shortened ID.
        str_uuid: The full UUID string. Required only if `aimbat_obj` is a class.

    Returns:
        str: The shortest unique prefix string, including hyphens where applicable.
    """

    if isinstance(aimbat_obj, type):
        model_class = aimbat_obj
        if str_uuid is None:
            raise ValueError("str_uuid must be provided when aimbat_obj is a class.")
        target_full = str(UUID(str_uuid))
    else:
        model_class = type(aimbat_obj)
        target_full = str(aimbat_obj.id)

    prefix_clean = target_full.replace("-", "")[:min_length]

    # select with a WHERE clause that removes dashes and compares the cleaned prefix
    statement = select(model_class.id).where(
        func.replace(cast(model_class.id, String), "-", "").like(f"{prefix_clean}%")
    )

    # Store results as standard hyphenated strings
    results = session.exec(statement).all()
    relevant_pool = [str(uid) for uid in results]

    if target_full not in relevant_pool:
        raise ValueError(f"ID {target_full} not found in table {model_class.__name__}")

    current_length = min_length
    while current_length < len(target_full):
        candidate = target_full[:current_length]
        if candidate.endswith("-"):
            current_length += 1
            candidate = target_full[:current_length]

        matches = [u for u in relevant_pool if u.startswith(candidate)]
        if len(matches) == 1:
            return candidate
        current_length += 1

    return target_full
