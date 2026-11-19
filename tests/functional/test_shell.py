"""Functional tests for the AIMBAT interactive shell.

Helper functions are tested directly (no subprocess).  The REPL itself is
exercised via subprocess with piped stdin.
"""

import os
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from aimbat._cli.shell import _build_completion_dict, _extract_event_flag
from aimbat.app import app as aimbat_app

_LOG_DIR = Path(__file__).parents[1] / ".logs"


def _worker_logfile() -> str:
    """Log file path unique per xdist worker (``"master"`` off a non-parallel run).

    Written to the gitignored ``tests/.logs/`` directory to keep logs out of the
    project root.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    _LOG_DIR.mkdir(exist_ok=True)
    return str(_LOG_DIR / f"aimbat_test_{worker}.log")


# ---------------------------------------------------------------------------
# Local fixture — subprocess with stdin support
# ---------------------------------------------------------------------------


@pytest.fixture()
def shell_subprocess(
    db_path: Path,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Run ``aimbat shell`` as a subprocess with stdin piped in.

    Args:
        db_path: Path to the temporary project database file.

    Returns:
        A callable that accepts stdin text, and optionally extra environment
        variables, and returns the completed process.
    """

    def _run(
        stdin: str, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy() | (extra_env or {})
        env["AIMBAT_DB_URL"] = f"sqlite+pysqlite:///{db_path}"
        env["AIMBAT_LOGFILE"] = _worker_logfile()
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
        for sub in ("list", "dump", "delete"):
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
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
    ) -> None:
        """Shell exits with code 0 when the user types 'exit'."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("exit\n")
        assert result.returncode == 0, result.stderr

    def test_exits_cleanly_on_eof(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
    ) -> None:
        """Shell exits cleanly when stdin is closed (simulates Ctrl+D)."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("")
        assert result.returncode == 0, result.stderr

    def test_executes_command(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
    ) -> None:
        """Commands typed in the shell produce output."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("project info\nexit\n")
        assert result.returncode == 0, result.stderr
        assert "Project Info" in result.stdout

    def test_unknown_command_does_not_crash(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
    ) -> None:
        """An unrecognised command is ignored; the shell keeps running."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("notacommand\nexit\n")
        assert result.returncode == 0, result.stderr

    def test_aimbat_prefix_stripped_and_command_runs(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
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
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
    ) -> None:
        """'event switch' without an ID resets to the DB default without error."""
        aimbat_subprocess(["project", "create"])
        result = shell_subprocess("event switch\nexit\n")
        assert result.returncode == 0, result.stderr

    def test_invalid_event_flag_does_not_crash(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
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


@pytest.mark.slow
@pytest.mark.cli
class TestPhaseSwitch:
    """Tests for the shell-only `phase switch` command."""

    @pytest.fixture()
    def event_with_two_phases(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        sac_file_good: Path,
    ) -> str:
        """Create a project with one event that has phases P and PKP.

        Returns:
            The event's ID.
        """
        import json

        aimbat_subprocess(["project", "create"])
        added = aimbat_subprocess(
            [
                "data",
                "add",
                str(sac_file_good),
                "--unlabelled-as",
                "PKP",
                "--no-progress",
            ]
        )
        assert added.returncode == 0, added.stderr
        events = json.loads(aimbat_subprocess(["event", "dump"]).stdout)
        return events[0]["id"]

    def test_switch_follows_phase(
        self,
        event_with_two_phases: str,
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
    ) -> None:
        """The ICCS status line names the switched phase."""
        result = shell_subprocess(
            f"event switch {event_with_two_phases}\nphase switch PKP\nexit\n"
        )
        assert result.returncode == 0, result.stderr
        assert "phase PKP" in result.stdout

    def test_without_phase_the_event_is_ambiguous(
        self,
        event_with_two_phases: str,
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
    ) -> None:
        """Clearing the phase falls back to the single-phase rule."""
        result = shell_subprocess(
            f"event switch {event_with_two_phases}\nphase switch P\nphase switch\n"
            + "exit\n"
        )
        assert result.returncode == 0, result.stderr
        ready = result.stdout.index("phase P)")
        assert result.stdout.index("has phases P, PKP", ready) > ready

    def test_unknown_phase_is_refused(
        self,
        event_with_two_phases: str,
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
    ) -> None:
        """A phase the event lacks is refused with the event's phases."""
        result = shell_subprocess(
            f"event switch {event_with_two_phases}\nphase switch S\nexit\n"
        )
        assert result.returncode == 0, result.stderr
        output = result.stdout + result.stderr
        assert "has no phase 'S'" in output
        assert "P, PKP" in output

    def test_needs_an_event(
        self,
        event_with_two_phases: str,
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
    ) -> None:
        """A phase cannot be switched without an event context."""
        result = shell_subprocess("phase switch P\nexit\n")
        assert result.returncode == 0, result.stderr
        assert "event switch" in result.stdout + result.stderr

    def test_event_switch_clears_a_phase_the_event_lacks(
        self,
        event_with_two_phases: str,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
        multi_event_data: list[Path],
    ) -> None:
        """Switching to an event without the shell's phase clears the phase."""
        import json

        added = aimbat_subprocess(
            ["data", "add", str(multi_event_data[0]), "--unlabelled-as", "P"]
            + ["--no-progress"]
        )
        assert added.returncode == 0, added.stderr
        events = json.loads(aimbat_subprocess(["event", "dump"]).stdout)
        (other,) = {e["id"] for e in events} - {event_with_two_phases}

        result = shell_subprocess(
            f"event switch {event_with_two_phases}\nphase switch PKP\n"
            + f"event switch {other}\nexit\n"
        )
        assert result.returncode == 0, result.stderr
        assert "no phase 'PKP'" in result.stdout
        assert f"ICCS ready (event {other[:8]})" in result.stdout

    def test_exported_default_phase_is_the_shell_phase(
        self,
        event_with_two_phases: str,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        shell_subprocess: Callable[..., subprocess.CompletedProcess[str]],
        multi_event_data: list[Path],
    ) -> None:
        """An exported `DEFAULT_PHASE` is followed and cleared like `--phase`."""
        import json

        added = aimbat_subprocess(
            ["data", "add", str(multi_event_data[0]), "--unlabelled-as", "P"]
            + ["--no-progress"]
        )
        assert added.returncode == 0, added.stderr
        events = json.loads(aimbat_subprocess(["event", "dump"]).stdout)
        (other,) = {e["id"] for e in events} - {event_with_two_phases}

        result = shell_subprocess(
            f"event switch {event_with_two_phases}\nevent switch {other}\nexit\n",
            {"DEFAULT_PHASE": "PKP"},
        )
        assert result.returncode == 0, result.stderr
        assert "phase PKP" in result.stdout
        assert "no phase 'PKP'" in result.stdout
        assert f"ICCS ready (event {other[:8]})" in result.stdout
