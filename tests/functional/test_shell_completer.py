"""Functional tests for `aimbat shell` tab completion of argument values."""

import shlex
from uuid import UUID

import pytest
from prompt_toolkit.completion import CompleteEvent, Completion
from prompt_toolkit.document import Document
from sqlalchemy import Engine
from sqlmodel import Session, select

from aimbat._cli._shell_completer import ShellCompleter
from aimbat._cli.shell import _shell_completer
from aimbat.app import app as aimbat_app
from aimbat.core import create_snapshot
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatSnapshot
from aimbat.utils import string_to_uuid


@pytest.fixture()
def completer(loaded_engine: Engine) -> ShellCompleter:
    """The shell's completer over the multi-event test project.

    Args:
        loaded_engine: The patched engine with multi-event data loaded.

    Returns:
        The completer, as `aimbat shell` builds it.
    """
    return _shell_completer(aimbat_app)


def _complete(completer: ShellCompleter, text: str) -> list[Completion]:
    return list(completer.get_completions(Document(text), CompleteEvent()))


def _ids(completer: ShellCompleter, text: str) -> list[str]:
    """Return the completions for `text` that aren't options."""
    return [c.text for c in _complete(completer, text) if not c.text.startswith("-")]


def _all_ids(engine: Engine, model_class: type) -> set[UUID]:
    with Session(engine) as session:
        return set(session.exec(select(model_class.id)).all())  # type: ignore[attr-defined]


def _resolve(engine: Engine, model_class: type, prefixes: list[str]) -> set[UUID]:
    assert prefixes, "no IDs offered"
    with Session(engine) as session:
        return {string_to_uuid(session, p, model_class) for p in prefixes}


class TestIdCompletion:
    """Tests for which IDs are offered where."""

    def test_event_switch_offers_every_event(
        self, completer: ShellCompleter, loaded_engine: Engine
    ) -> None:
        """Verifies `event switch` offers resolvable IDs of all events, with times.

        Args:
            completer: The shell completer.
            loaded_engine: The patched engine with multi-event data loaded.
        """
        completions = _complete(completer, "event switch ")
        prefixes = [c.text for c in completions]
        assert _resolve(loaded_engine, AimbatEvent, prefixes) == _all_ids(
            loaded_engine, AimbatEvent
        )
        assert all(c.display_meta_text for c in completions)

    def test_typed_prefix_narrows_the_choices(self, completer: ShellCompleter) -> None:
        """Verifies only IDs starting with the typed text are offered.

        Args:
            completer: The shell completer.
        """
        first = _ids(completer, "event switch ")[0]
        assert _ids(completer, f"event switch {first}") == [first]

    def test_positional_id_offers_ids_and_options(
        self, completer: ShellCompleter, loaded_engine: Engine
    ) -> None:
        """Verifies a positional ID slot offers seismogram IDs alongside options.

        Args:
            completer: The shell completer.
            loaded_engine: The patched engine with multi-event data loaded.
        """
        completions = [c.text for c in _complete(completer, "seismogram delete ")]
        ids = [c for c in completions if not c.startswith("-")]
        assert _resolve(loaded_engine, AimbatSeismogram, ids) == _all_ids(
            loaded_engine, AimbatSeismogram
        )
        assert "--yes" in completions

    def test_option_value_offers_only_ids(self, completer: ShellCompleter) -> None:
        """Verifies the value of `--id` is completed with IDs and nothing else.

        Args:
            completer: The shell completer.
        """
        completions = _complete(completer, "seismogram parameter get --id ")
        assert completions
        assert not any(c.text.startswith("-") for c in completions)

    def test_option_equals_form(self, completer: ShellCompleter) -> None:
        """Verifies `--event=<prefix>` completes the part after `=`.

        Args:
            completer: The shell completer.
        """
        first = _ids(completer, "event switch ")[0]
        text = f"seismogram list --event={first[0]}"
        completions = _complete(completer, text)
        assert first in [c.display_text for c in completions]
        assert f"--event={first}" in [_accept(text, c)[-1] for c in completions]

    def test_all_offered_where_accepted(self, completer: ShellCompleter) -> None:
        """Verifies "all" is offered for event arguments that accept it.

        Args:
            completer: The shell completer.
        """
        assert "all" in _ids(completer, "seismogram list --event ")
        assert "all" not in _ids(completer, "event switch ")

    def test_snapshot_ids(
        self, completer: ShellCompleter, loaded_engine: Engine
    ) -> None:
        """Verifies snapshot commands complete snapshot IDs, with their comments.

        Args:
            completer: The shell completer.
            loaded_engine: The patched engine with multi-event data loaded.
        """
        with Session(loaded_engine) as session:
            for event in session.exec(select(AimbatEvent)).all():
                create_snapshot(session, event, comment="before ICCS")
        completions = [
            c for c in _complete(completer, "snapshot delete ") if c.text[0] != "-"
        ]
        assert len(completions) == len(_all_ids(loaded_engine, AimbatEvent))
        assert _resolve(
            loaded_engine, AimbatSnapshot, [c.text for c in completions]
        ) == _all_ids(loaded_engine, AimbatSnapshot)
        assert all(c.display_meta_text.endswith("before ICCS") for c in completions)

    @pytest.mark.parametrize(
        "text",
        [
            "station list --station ",  # unknown option
            "seismogram delete --",  # an option is being typed
        ],
    )
    def test_no_ids_offered(self, text: str, completer: ShellCompleter) -> None:
        """Verifies no IDs appear after an unknown option or while typing one.

        Args:
            text: Text before the cursor.
            completer: The shell completer.
        """
        assert _ids(completer, text) == []

    def test_command_group_offers_only_subcommands(
        self, completer: ShellCompleter
    ) -> None:
        """Verifies a command group offers its subcommands, including `switch`.

        Args:
            completer: The shell completer.
        """
        completions = _complete(completer, "event ")
        assert {"switch", "list", "parameter"} <= {c.text for c in completions}
        assert not any(c.display_meta_text for c in completions), "no IDs"

    def test_top_level_offers_exit_but_not_shell(
        self, completer: ShellCompleter
    ) -> None:
        """Verifies `exit` is offered and commands useless in the shell are not.

        Args:
            completer: The shell completer.
        """
        assert [c.text for c in _complete(completer, "ex")] == ["exit"]
        assert "shell" not in [c.text for c in _complete(completer, "")]
        assert "completion" not in [c.text for c in _complete(completer, "utils ")]

    def test_shell_event_narrows_seismograms_and_snapshots(
        self,
        completer: ShellCompleter,
        loaded_engine: Engine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies the shell's event context limits seismogram and snapshot IDs.

        Args:
            completer: The shell completer.
            loaded_engine: The patched engine with multi-event data loaded.
            monkeypatch: The pytest monkeypatch fixture.
        """
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            event_id = event.id
            expected = set(
                session.exec(
                    select(AimbatSeismogram.id).where(
                        AimbatSeismogram.event_id == event_id
                    )
                ).all()
            )
        monkeypatch.setenv("DEFAULT_EVENT_ID", str(event_id))
        ids = _ids(completer, "seismogram delete ")
        assert _resolve(loaded_engine, AimbatSeismogram, ids) == expected
        assert expected != _all_ids(loaded_engine, AimbatSeismogram)


class TestChoiceCompletion:
    """Tests for arguments with a fixed set of values."""

    @pytest.mark.parametrize(
        "text",
        [
            "seismogram parameter get ",  # positional
            "seismogram parameter get --name ",  # option value
        ],
    )
    def test_parameter_names_offered(
        self, text: str, completer: ShellCompleter
    ) -> None:
        """Verifies every seismogram parameter name is offered.

        Args:
            text: Text before the cursor.
            completer: The shell completer.
        """
        from aimbat.types import SeismogramParameter

        # cyclopts' names for enum members: lower case, `_` as `-`.
        names = {p.name.lower().replace("_", "-") for p in SeismogramParameter}
        assert names <= set(_ids(completer, text))

    def test_typed_text_narrows_the_choices(self, completer: ShellCompleter) -> None:
        """Verifies only choices starting with the typed text are offered.

        Args:
            completer: The shell completer.
        """
        assert _ids(completer, "event parameter set window") == [
            "window-pre",
            "window-post",
        ]

    def test_option_equals_form(self, completer: ShellCompleter) -> None:
        """Verifies `--type=<prefix>` completes the part after `=`.

        Args:
            completer: The shell completer.
        """
        text = "data add --type=json"
        completions = _complete(completer, text)
        assert [c.display_text for c in completions] == ["json-event", "json-station"]
        assert _accept(text, completions[0])[-1] == "--type=json-event"

    def test_free_text_value_offers_nothing(self, completer: ShellCompleter) -> None:
        """Verifies the value of an option without fixed choices isn't completed.

        Args:
            completer: The shell completer.
        """
        text = "event parameter set window-pre --value "
        assert _complete(completer, text) == []


class TestOptionCompletion:
    """Tests for which options are offered as an argument list fills up."""

    @pytest.mark.parametrize(
        "text",
        [
            "seismogram parameter get select ",  # name given positionally
            "seismogram parameter get --name select ",  # name given as option
        ],
    )
    def test_options_follow_a_filled_argument(
        self, text: str, completer: ShellCompleter
    ) -> None:
        """Verifies the remaining options follow, and the name isn't offered again.

        Args:
            text: Text before the cursor.
            completer: The shell completer.
        """
        texts = [c.text for c in _complete(completer, text)]
        assert "--id" in texts
        assert "--name" not in texts
        assert "select" not in texts

    def test_given_options_not_repeated(self, completer: ShellCompleter) -> None:
        """Verifies an option already on the line isn't offered again.

        Args:
            completer: The shell completer.
        """
        texts = [c.text for c in _complete(completer, "seismogram list --raw ")]
        assert "--raw" not in texts
        assert "--no-raw" not in texts
        assert "--debug" in texts

    def test_free_text_value_offers_only_remaining_options(
        self, completer: ShellCompleter
    ) -> None:
        """Verifies a value with no fixed choices is followed by the other options.

        Args:
            completer: The shell completer.
        """
        texts = [c.text for c in _complete(completer, "event parameter set min-cc ")]
        assert texts
        assert all(t.startswith("-") for t in texts)
        assert "--value" in texts

    def test_help_flags_not_offered(self, completer: ShellCompleter) -> None:
        """Verifies `--help` is left out, as it is for command groups.

        Args:
            completer: The shell completer.
        """
        texts = [c.text for c in _complete(completer, "seismogram list --")]
        assert "--help" not in texts
        assert "-h" not in texts


class TestArgumentBoundaries:
    """Tests for later positionals, `--` and options taking several values."""

    def test_second_positional_offers_no_ids(self, completer: ShellCompleter) -> None:
        """Verifies the comment of `snapshot create` isn't completed with IDs.

        Args:
            completer: The shell completer.
        """
        event = _ids(completer, "event switch ")[0]
        texts = [c.text for c in _complete(completer, f"snapshot create {event} ")]
        assert texts
        assert all(t.startswith("-") for t in texts)

    def test_all_offered_for_station_filter(self, completer: ShellCompleter) -> None:
        """Verifies "all" is offered where a station argument accepts it.

        Args:
            completer: The shell completer.
        """
        assert "all" in _ids(completer, "station quality list --station ")

    def test_no_options_after_end_of_options(self, completer: ShellCompleter) -> None:
        """Verifies `--` ends option completion.

        Args:
            completer: The shell completer.
        """
        assert _complete(completer, "seismogram parameter get select -- ") == []

    def test_positional_values_after_end_of_options(
        self, completer: ShellCompleter
    ) -> None:
        """Verifies a positional after `--` is still completed, without options.

        Args:
            completer: The shell completer.
        """
        texts = [c.text for c in _complete(completer, "seismogram delete -- ")]
        assert texts
        assert not any(t.startswith("-") for t in texts)
        assert [
            c.text for c in _complete(completer, "seismogram parameter set -- sel")
        ] == ["select"]

    def test_multi_value_option_not_mistaken_for_positionals(
        self, completer: ShellCompleter
    ) -> None:
        """Verifies every value after `--sources` belongs to it.

        Args:
            completer: The shell completer.
        """
        texts = [c.text for c in _complete(completer, "data add --sources a b ")]
        assert "--type" in texts
        assert "--sources" not in texts


def _accept(text: str, completion: Completion) -> list[str]:
    """Return the words of `text` once `completion` is accepted."""
    return shlex.split(text[: len(text) + completion.start_position] + completion.text)


class TestQuoting:
    """Tests for completing a word typed in quotes."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("seismogram parameter set 'sel", "select"),
            ('seismogram parameter set "sel', "select"),
            ('seismogram parameter set "sel"', "select"),
            ('seismogram parameter get --name="sel', "--name=select"),
        ],
    )
    def test_choice_in_quotes(
        self, completer: ShellCompleter, text: str, expected: str
    ) -> None:
        """Verifies a quoted choice is matched unquoted and completes to valid syntax.

        Args:
            completer: The shell completer.
            text: The line before the cursor.
            expected: The last word once the completion is accepted.
        """
        (completion,) = _complete(completer, text)
        assert completion.display_text == "select"
        assert _accept(text, completion)[-1] == expected

    def test_id_in_quotes(
        self, completer: ShellCompleter, loaded_engine: Engine
    ) -> None:
        """Verifies a quoted ID prefix completes to a resolvable ID.

        Args:
            completer: The shell completer.
            loaded_engine: The patched engine with multi-event data loaded.
        """
        short = _ids(completer, "event switch ")[0]
        text = f'event switch "{short[:2]}'
        completions = _complete(completer, text)
        accepted = [_accept(text, c) for c in completions]
        assert all(words[:2] == ["event", "switch"] for words in accepted)
        assert _resolve(loaded_engine, AimbatEvent, [w[-1] for w in accepted])

    def test_unsplittable_line(self, completer: ShellCompleter) -> None:
        """Verifies a line ending in a backslash offers nothing.

        Args:
            completer: The shell completer.
        """
        assert _complete(completer, "event switch \\") == []


class TestCaching:
    """Tests for when IDs are read from the database."""

    def test_ids_cached_until_invalidated(
        self, completer: ShellCompleter, loaded_engine: Engine
    ) -> None:
        """Verifies a deleted record disappears only after `invalidate`.

        Args:
            completer: The shell completer.
            loaded_engine: The patched engine with multi-event data loaded.
        """
        before = _ids(completer, "seismogram delete ")
        with Session(loaded_engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).first()
            assert seismogram is not None
            session.delete(seismogram)
            session.commit()

        assert _ids(completer, "seismogram delete ") == before
        completer.invalidate()
        assert len(_ids(completer, "seismogram delete ")) == len(before) - 1

    def test_shell_refreshes_ids_after_each_command(
        self,
        loaded_engine: Engine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies `aimbat shell` clears cached IDs after every command it runs.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            monkeypatch: The pytest monkeypatch fixture.
        """
        import importlib
        import io

        # The `_cli` package re-exports the `shell` App under the module's name.
        shell = importlib.import_module("aimbat._cli.shell")

        invalidations: list[int] = []
        real = shell._shell_completer

        def _spy(app: object) -> ShellCompleter:
            completer = real(aimbat_app)
            completer.invalidate = lambda: invalidations.append(1)
            return completer

        monkeypatch.setattr(shell, "_shell_completer", _spy)
        monkeypatch.setattr("sys.stdin", io.StringIO("event list\nstation list\n"))
        shell.cli_shell()  # Ends at end of input.
        assert len(invalidations) == 2

    def test_database_errors_leave_options_working(
        self, completer: ShellCompleter, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies an unreadable project means no IDs, not a broken prompt.

        Args:
            completer: The shell completer.
            monkeypatch: The pytest monkeypatch fixture.
        """

        def _fail(model_class: type) -> list[object]:
            raise RuntimeError("no project")

        monkeypatch.setattr("aimbat._cli._shell_completer._read_choices", _fail)
        completions = [c.text for c in _complete(completer, "seismogram delete ")]
        assert completions
        assert all(c.startswith("-") for c in completions)
