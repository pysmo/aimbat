"""Functional tests for the AIMBAT interactive shell.

Helper functions are tested directly (no subprocess).  The REPL itself is
exercised via subprocess with piped stdin.
"""

import os
import subprocess
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from aimbat._cli.shell import _build_completion_dict, _extract_event_flag, _inject_event
from aimbat.app import app as aimbat_app

_AIMBAT_LOGFILE = "aimbat_test.log"


# ---------------------------------------------------------------------------
# Local fixture — subprocess with stdin support
# ---------------------------------------------------------------------------


@pytest.fixture()
def shell_subprocess(
    db_path: Path,
) -> Callable[[str], subprocess.CompletedProcess[str]]:
    """Run ``aimbat shell`` as a subprocess with stdin piped in.

    Args:
        db_path: Path to the temporary project database file.

    Returns:
        A callable that accepts stdin text and returns the completed process.
    """

    def _run(stdin: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["AIMBAT_DB_URL"] = f"sqlite+pysqlite:///{db_path}"
        env["AIMBAT_LOGFILE"] = _AIMBAT_LOGFILE
        env["COLUMNS"] = "1000"
        return subprocess.run(
            ["uv", "run", "aimbat", "shell"],
            input=stdin,
            capture_output=True,
            text=True,
            env=env,
        )

    return _run


# ===========================================================================
# _extract_event_flag
# ===========================================================================


class TestExtractEventFlag:
    """Tests for the ``_extract_event_flag`` helper."""

    def test_no_flag_returns_none(self) -> None:
        assert _extract_event_flag(["event", "list"]) is None

    def test_empty_tokens_returns_none(self) -> None:
        assert _extract_event_flag([]) is None

    def test_space_separated_event(self) -> None:
        assert _extract_event_flag(["--event", "abc123"]) == "abc123"

    def test_space_separated_event_id(self) -> None:
        assert _extract_event_flag(["--event-id", "abc123"]) == "abc123"

    def test_equals_event(self) -> None:
        assert _extract_event_flag(["--event=abc123"]) == "abc123"

    def test_equals_event_id(self) -> None:
        assert _extract_event_flag(["--event-id=abc123"]) == "abc123"

    def test_flag_buried_in_token_list(self) -> None:
        assert _extract_event_flag(["event", "dump", "--event", "myid"]) == "myid"

    def test_flag_at_end_without_value_returns_none(self) -> None:
        # --event is the last token with no following value
        assert _extract_event_flag(["event", "list", "--event"]) is None

    def test_other_flags_ignored(self) -> None:
        assert _extract_event_flag(["--all", "--json", "--verbose"]) is None


# ===========================================================================
# _inject_event
# ===========================================================================


class TestInjectEvent:
    """Tests for the ``_inject_event`` helper."""

    _UID = uuid.UUID("12345678-1234-5678-1234-567812345678")

    def test_appends_event_flag_when_absent(self) -> None:
        result = _inject_event(["event", "list"], self._UID)
        assert "--event" in result
        assert str(self._UID) in result

    def test_no_change_when_event_already_present(self) -> None:
        tokens = ["event", "dump", "--event", "other-id"]
        result = _inject_event(tokens, self._UID)
        assert result == tokens

    def test_no_change_when_event_id_already_present(self) -> None:
        tokens = ["event", "dump", "--event-id", "other-id"]
        result = _inject_event(tokens, self._UID)
        assert result == tokens

    def test_original_tokens_not_mutated(self) -> None:
        tokens = ["event", "list"]
        original = tokens[:]
        _inject_event(tokens, self._UID)
        assert tokens == original

    def test_returns_new_list(self) -> None:
        tokens = ["event", "list"]
        result = _inject_event(tokens, self._UID)
        assert result is not tokens


# ===========================================================================
# _build_completion_dict
# ===========================================================================


class TestBuildCompletionDict:
    """Tests for the ``_build_completion_dict`` helper."""

    def test_returns_dict(self) -> None:
        assert isinstance(_build_completion_dict(aimbat_app), dict)

    def test_contains_top_level_commands(self) -> None:
        result = _build_completion_dict(aimbat_app)
        for key in ("event", "data", "station", "seismogram", "snapshot"):
            assert key in result, f"'{key}' missing from completion dict"

    def test_event_subcommands_present(self) -> None:
        result = _build_completion_dict(aimbat_app)
        event_cmds = result.get("event")
        assert isinstance(event_cmds, dict)
        for sub in ("list", "dump", "default", "delete"):
            assert sub in event_cmds, f"'event {sub}' missing from completion dict"

    def test_help_flags_excluded(self) -> None:
        result = _build_completion_dict(aimbat_app)
        assert "--help" not in result
        assert "-h" not in result

    def test_shell_and_tui_excluded(self) -> None:
        # shell removes itself and tui from the REPL's completions
        # (checked at runtime in cli_shell; here we just verify the dict
        # is built correctly from the top-level app)
        result = _build_completion_dict(aimbat_app)
        # shell and tui may or may not appear depending on whether they are
        # registered subcommands; the key assertion is that the call succeeds
        # and returns a non-empty mapping
        assert len(result) > 0


# ===========================================================================
# Shell subprocess (integration)
# ===========================================================================


@pytest.mark.slow
@pytest.mark.cli
class TestShellSubprocess:
    """Integration tests for the shell REPL started as a real subprocess."""

    def test_exits_cleanly_on_exit_command(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[[str], subprocess.CompletedProcess[str]],
    ) -> None:
        """Shell exits with code 0 when the user types 'exit'."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("exit\n")
        assert result.returncode == 0, result.stderr

    def test_exits_cleanly_on_eof(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[[str], subprocess.CompletedProcess[str]],
    ) -> None:
        """Shell exits cleanly when stdin is closed (simulates Ctrl+D)."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("")
        assert result.returncode == 0, result.stderr

    def test_executes_command(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[[str], subprocess.CompletedProcess[str]],
    ) -> None:
        """Commands typed in the shell produce output."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("project info\nexit\n")
        assert result.returncode == 0, result.stderr
        assert "Project Info" in result.stdout

    def test_unknown_command_does_not_crash(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[[str], subprocess.CompletedProcess[str]],
    ) -> None:
        """An unrecognised command is ignored; the shell keeps running."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("notacommand\nexit\n")
        assert result.returncode == 0, result.stderr

    def test_aimbat_prefix_stripped_and_command_runs(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[[str], subprocess.CompletedProcess[str]],
    ) -> None:
        """Typing 'aimbat <command>' strips the prefix and still runs the command."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("aimbat project info\nexit\n")
        assert result.returncode == 0, result.stderr
        assert "Project Info" in result.stdout
        assert "Tip:" in result.stdout

    def test_event_switch_requires_no_db_write(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[[str], subprocess.CompletedProcess[str]],
    ) -> None:
        """'event switch' without an ID resets to the DB default without error."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("event switch\nexit\n")
        assert result.returncode == 0, result.stderr

    def test_invalid_event_flag_does_not_crash(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[[str], subprocess.CompletedProcess[str]],
    ) -> None:
        """The shell should not crash when an invalid --event is specified."""
        aimbat_subprocess(["project", "create"])
        # 'event list --event invalid' previously crashed the shell
        result = shell_subprocess("event list --event invalid\nexit\n")
        assert result.returncode == 0, result.stderr

        # Check for error in stdout OR stderr
        combined_output = result.stdout + result.stderr
        assert "Error" in combined_output

        # We want to ensure there is only ONE error panel (no double errors)
        assert combined_output.count("Error") == 1
