"""Read and write notes attached to events, stations, seismograms, or snapshots."""

import uuid
from typing import Literal

from sqlmodel import Session, select

from aimbat.models import AimbatNote

__all__ = ["get_note_content", "save_note"]

NoteTarget = Literal["event", "station", "seismogram", "snapshot"]


def get_note_content(session: Session, target: NoteTarget, target_id: uuid.UUID) -> str:
    """Return the note content for the given entity.

    Args:
        session: Active database session.
        target: Entity type — one of `event`, `station`, `seismogram`, `snapshot`.
        target_id: UUID of the target entity.

    Returns:
        Markdown note content, or an empty string if no note exists yet.
    """
    attr = getattr(AimbatNote, f"{target}_id")
    note = session.exec(select(AimbatNote).where(attr == target_id)).first()
    return note.content if note is not None else ""


def save_note(
    session: Session, target: NoteTarget, target_id: uuid.UUID, content: str
) -> None:
    """Save note content for the given entity, creating the note record if needed.

    Args:
        session: Active database session.
        target: Entity type — one of `event`, `station`, `seismogram`, `snapshot`.
        target_id: UUID of the target entity.
        content: Markdown note content to save.
    """
    attr = getattr(AimbatNote, f"{target}_id")
    note = session.exec(select(AimbatNote).where(attr == target_id)).first()
    if note is None:
        note = AimbatNote(**{f"{target}_id": target_id, "content": content})
    else:
        note.content = content
    session.add(note)
    session.commit()
