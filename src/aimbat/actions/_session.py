"""Session handling shared by the actions."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, SQLModel, col, select


@contextmanager
def discard_cached_iccs_on_failure(phase_id: UUID) -> Iterator[None]:
    """Evict the phase's cached ICCS instance if the enclosed block raises.

    The interactive tools apply new values to the cached instance before they
    are stored. If storing them fails, the instance holds values the database
    refused, yet its instance digest still matches the stored parameters, so
    it would not be rebuilt.
    """
    try:
        yield
    except Exception:
        from aimbat.core import evict_iccs_cache_entry

        evict_iccs_cache_entry(phase_id)
        raise


@contextmanager
def open_session(engine: Engine | None) -> Iterator[Session]:
    """Open a session on `engine`, or on `aimbat.db.engine` if it is None."""
    if engine is None:
        from aimbat.db import engine

    with Session(engine) as session:
        yield session


def require_ids(
    session: Session, model: type[SQLModel], ids: Sequence[UUID]
) -> list[UUID]:
    """Return `ids` with duplicates removed, after checking each one exists.

    Raises:
        NoResultFound: If any ID has no matching `model` record. The message
            lists every missing ID.
    """
    unique = list(dict.fromkeys(ids))
    if not unique:
        return unique
    id_column = col(getattr(model, "id"))
    found = set(session.exec(select(id_column).where(id_column.in_(unique))).all())
    missing = [i for i in unique if i not in found]
    if missing:
        label = model.__name__.removeprefix("Aimbat").lower()
        noun = "ID" if len(missing) == 1 else "IDs"
        raise NoResultFound(
            f"No {label} found with {noun} " + ", ".join(map(str, missing)) + "."
        )
    return unique
