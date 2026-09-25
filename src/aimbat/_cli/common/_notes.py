"""Build the `note` sub-app shared by the event, seismogram, station and snapshot CLIs."""

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from cyclopts import App, Parameter

from ._decorators import handle_issues, print_warning
from ._parameters import DebugParameter, open_in_editor

if TYPE_CHECKING:
    from sqlmodel import Session

    from aimbat.core import NoteTarget
    from aimbat.models import AimbatTypes

__all__ = ["make_note_app"]

_EDIT_HELP = """Open the {target} note in `$EDITOR` and save changes on exit.

The note is written to a temporary Markdown file. When the editor closes,
the updated content is saved back to the database. If the file is left
unchanged, no write is performed.

On Windows, set the `EDITOR` environment variable to your preferred editor
(e.g. `notepad`, `notepad++`). The editor must be a blocking process; for
GUI editors that do not block by default (such as VS Code), pass the
appropriate wait flag (e.g. `EDITOR="code --wait"`).
"""


def _resolve_record(
    session: "Session", model: type["AimbatTypes"], record_id: UUID
) -> UUID:
    """Return `record_id`, having checked the record it names exists."""
    from sqlalchemy.exc import NoResultFound

    if session.get(model, record_id) is None:
        raise NoResultFound(f"No {model.__name__} found with id: {record_id}.")
    return record_id


def make_note_app(
    target: "NoteTarget", model: type["AimbatTypes"], parameter: Parameter
) -> App:
    """Build the `note` sub-app (`read` and `edit`) for one kind of record.

    Args:
        target: The kind of record the notes belong to, also the noun used in
            the commands' help text.
        model: Model class the note is attached to.
        parameter: cyclopts parameter that selects the record to act on.
    """
    note_app = App(
        name="note", help=f"Read and edit {target} notes.", help_format="markdown"
    )
    article = "an" if target.startswith(("a", "e", "i", "o", "u")) else "a"

    def read(
        record_id: Annotated[UUID, parameter],
        *,
        _: DebugParameter = DebugParameter(),
    ) -> None:
        from rich.console import Console
        from rich.markdown import Markdown
        from sqlmodel import Session

        from aimbat.core import get_note_content
        from aimbat.db import engine

        with Session(engine) as session:
            content = get_note_content(
                session, target, _resolve_record(session, model, record_id)
            )

        Console().print(Markdown(content) if content else "(no note)")

    def edit(
        record_id: Annotated[UUID, parameter],
        *,
        _: DebugParameter = DebugParameter(),
    ) -> None:
        from sqlmodel import Session

        from aimbat.core import get_note_content, save_note
        from aimbat.db import engine

        with Session(engine) as session:
            original = get_note_content(
                session, target, _resolve_record(session, model, record_id)
            )

        updated = open_in_editor(original)

        if updated != original:
            with Session(engine) as session:
                raced = save_note(
                    session, target, record_id, updated, expected_previous=original
                )
            if raced:
                print_warning(
                    "Note changed elsewhere while the editor was open; your edit has"
                    + " overwritten that change."
                )

    read.__doc__ = (
        f"Display the note attached to {article} {target}, rendered as Markdown."
    )
    edit.__doc__ = _EDIT_HELP.format(target=target)

    note_app.command(handle_issues(read), name="read")
    note_app.command(handle_issues(edit), name="edit")

    return note_app
