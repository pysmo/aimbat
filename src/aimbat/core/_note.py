"""Read and write notes attached to events, stations, seismograms, or snapshots."""

import uuid
from typing import Literal, get_args

from sqlmodel import Session, select
from sqlmodel.sql.expression import ColumnElement

from aimbat.models import AimbatNote

__all__ = ["NoteTarget", "get_note_content", "save_note"]

NoteTarget = Literal["event", "station", "seismogram", "snapshot"]


def _note_id_attr(target: NoteTarget) -> ColumnElement[uuid.UUID]:
    """Return the `AimbatNote` foreign-key column for a note target.

    Guards against an untyped caller passing a `target` that isn't one of
    `NoteTarget`'s literal values, which `getattr` would otherwise resolve
    to an unrelated (or missing) attribute.
    """
    if target not in get_args(NoteTarget):
        raise ValueError(f"Invalid note target: {target!r}")
    return getattr(AimbatNote, f"{target}_id")


def get_note_content(session: Session, target: NoteTarget, target_id: uuid.UUID) -> str:
    """Return the note content for the given entity.

    Args:
        session: Active database session.
        target: Entity type, one of `event`, `station`, `seismogram`, `snapshot`.
        target_id: UUID of the target entity.

    Returns:
        Markdown note content, or an empty string if no note exists yet.
    """
    attr = _note_id_attr(target)
    note = session.exec(select(AimbatNote).where(attr == target_id)).one_or_none()
    return note.content if note is not None else ""


def save_note(
    session: Session, target: NoteTarget, target_id: uuid.UUID, content: str
) -> None:
    """Save note content for the given entity, creating the note record if needed.

    Args:
        session: Active database session.
        target: Entity type, one of `event`, `station`, `seismogram`, `snapshot`.
        target_id: UUID of the target entity.
        content: Markdown note content to save.
    """
    attr = _note_id_attr(target)
    note = session.exec(select(AimbatNote).where(attr == target_id)).one_or_none()
    if note is None:
        note = AimbatNote(**{f"{target}_id": target_id, "content": content})
    else:
        note.content = content
    session.add(note)
    session.commit()
