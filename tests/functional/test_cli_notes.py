"""Functional tests for the `note` sub-app shared by the entity CLI modules.

All four `note` apps are built by one factory, so these tests run the same
checks against each of them: what is written through `note edit` comes back
out of `note read`, and an ID that matches no record is reported rather than
answered with an empty note.
"""

import shlex
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound

_NOTE_BODY = "a note, written by the editor"


def _target_id(
    target: str, cli_json: Callable[[str], list[Any] | dict[str, Any]]
) -> str:
    """Return the ID of a record of the given kind to attach a note to."""
    if target == "snapshot":
        data = cli_json("snapshot dump")
        assert isinstance(data, dict)
        return str(data["snapshots"][0]["id"])
    records = cli_json(f"{target} dump")
    assert isinstance(records, list)
    return str(records[0]["id"])


@pytest.fixture()
def editor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point `$EDITOR` at a script that overwrites the note with a known body."""
    script = tmp_path / "fake_editor.py"
    script.write_text(
        "import sys\n"
        + f"open(sys.argv[1], 'w', encoding='utf-8').write({_NOTE_BODY!r})\n"
    )
    monkeypatch.setenv(
        "EDITOR", f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
    )
    monkeypatch.delenv("VISUAL", raising=False)


@pytest.mark.cli
@pytest.mark.parametrize("target", ["event", "station", "seismogram", "snapshot"])
class TestNoteCommands:
    """Tests for `<target> note read` and `<target> note edit`."""

    def test_edited_note_is_read_back(
        self,
        target: str,
        loaded_engine: Engine,
        editor: None,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list[Any] | dict[str, Any]],
        event_id: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies a note written through the editor is what `note read` prints.

        Args:
            target: The kind of record the note is attached to.
            loaded_engine: The monkeypatched engine with data loaded.
            editor: The fake `$EDITOR`.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            event_id: ID of the event a snapshot is created for.
            capsys: The pytest capsys fixture.
        """
        cli(f"snapshot create --event-id {event_id}")
        record_id = _target_id(target, cli_json)

        cli(f"{target} note read {record_id}")
        assert "(no note)" in capsys.readouterr().out, (
            "A record without a note should say so"
        )

        cli(f"{target} note edit {record_id}")

        cli(f"{target} note read {record_id}")
        assert "written by the editor" in capsys.readouterr().out, (
            "The edited note should be what is read back"
        )

    def test_unknown_id_is_reported(
        self,
        target: str,
        loaded_engine: Engine,
        editor: None,
        cli: Callable[[str], None],
        event_id: str,
    ) -> None:
        """Verifies an ID matching no record fails instead of reading an empty note.

        Args:
            target: The kind of record the note is attached to.
            loaded_engine: The monkeypatched engine with data loaded.
            editor: The fake `$EDITOR`.
            cli: The in-process CLI callable.
            event_id: ID of the event a snapshot is created for.
        """
        cli(f"snapshot create --event-id {event_id}")
        missing = uuid.uuid4()

        # Debug mode lets the error through as itself; otherwise `handle_issues`
        # turns it into a styled panel and a non-zero exit.
        with pytest.raises((SystemExit, NoResultFound)):
            cli(f"{target} note read {missing}")
        with pytest.raises((SystemExit, NoResultFound)):
            cli(f"{target} note edit {missing}")
