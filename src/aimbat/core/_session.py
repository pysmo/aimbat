"""Session helpers shared by the core modules."""

from sqlmodel import Session


def flush_deletes(session: Session) -> None:
    """Flush pending deletes, then expire every loaded instance.

    Deletes rely on the database's `ON DELETE CASCADE` and `SET NULL`, which
    the identity map does not see. Expiring makes the next access reload what
    the database now holds. Nothing is pending after the flush, so expiring
    discards no change.
    """
    session.flush()
    session.expire_all()
