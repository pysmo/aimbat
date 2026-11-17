"""Actions that modify notes."""

from uuid import UUID

from sqlalchemy import Engine

from aimbat import core
from aimbat.core import NoteTarget

from ._session import open_session

__all__ = ["save_note"]


def save_note(
    target: NoteTarget,
    target_id: UUID,
    content: str,
    *,
    expected_previous: str | None = None,
    engine: Engine | None = None,
) -> bool:
    """Save the note attached to an event, station, seismogram or snapshot.

    Args:
        target: Type of record the note is attached to.
        target_id: ID of that record.
        content: New note content, in Markdown.
        expected_previous: Note content the caller read before editing. If
            given and the stored note no longer matches it, the note is
            saved regardless and the mismatch is reported.
        engine: Engine to use. Defaults to the project engine.

    Returns:
        True if `expected_previous` was given and differed from the stored
        note, so that a concurrent edit was overwritten. False otherwise.
    """
    with open_session(engine) as session:
        raced = core.save_note(
            session, target, target_id, content, expected_previous=expected_previous
        )
        session.commit()
    return raced
