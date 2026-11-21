"""Tests for the shared CLI test helpers."""

import io
import subprocess
from collections.abc import Sequence

import pytest
from rich import box
from rich.console import Console
from rich.panel import Panel

from aimbat._cli.common._decorators import print_error_panel

from testsupport.cli import error_text, project_dump

_MESSAGE = (
    "Event 1a2b has phases P, pP. Name one with --phase or DEFAULT_PHASE, "
    "for example `aimbat align iccs --phase pP`."
)


def _render(panel_box: box.Box, width: int = 40) -> str:
    """Render the message in an error panel, as `print_error_panel` does."""
    file = io.StringIO()
    console = Console(file=file, width=width, color_system=None)
    console.print(
        Panel(_MESSAGE, title="Error", title_align="left", box=panel_box, expand=True)
    )
    return file.getvalue()


class TestErrorText:
    """`error_text` removes panel borders and collapses whitespace."""

    @pytest.mark.parametrize(
        "panel_box",
        [box.ROUNDED, box.SQUARE, box.HEAVY, box.DOUBLE, box.ASCII],
        ids=["rounded", "square", "heavy", "double", "ascii"],
    )
    def test_box_styles(self, panel_box: box.Box) -> None:
        assert error_text(_render(panel_box)) == f"Error {_MESSAGE}"

    def test_crlf(self) -> None:
        rendered = _render(box.ROUNDED).replace("\n", "\r\n")
        assert error_text(rendered) == f"Error {_MESSAGE}"

    @pytest.mark.parametrize("width", [30, 60, 200])
    def test_wrapped_lines(self, width: int) -> None:
        assert error_text(_render(box.ROUNDED, width)) == f"Error {_MESSAGE}"

    def test_plain_text(self) -> None:
        assert error_text("  one\n\ntwo   three \n") == "one two three"

    def test_error_panel(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("COLUMNS", "50")
        print_error_panel(ValueError(_MESSAGE))
        assert _MESSAGE in error_text(capsys.readouterr().err)


def _runner(
    returncode: int, stdout: str = "", stderr: str = ""
) -> "subprocess.CompletedProcess[str]":
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class TestProjectDump:
    """`project_dump` parses JSON and fails loudly on a non-zero exit."""

    def test_parses_json(self) -> None:
        seen: list[Sequence[str]] = []

        def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
            seen.append(command)
            return _runner(0, '[{"name": "P"}]')

        assert project_dump(run, ["phase", "dump"]) == [{"name": "P"}]
        assert seen == [["phase", "dump"]]

    def test_non_zero_exit_raises_with_stderr(self) -> None:
        def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
            return _runner(1, "", "no project found")

        with pytest.raises(AssertionError, match="exited with 1") as exc_info:
            project_dump(run, ["event", "dump"])
        assert "`aimbat event dump`" in str(exc_info.value)
        assert "no project found" in str(exc_info.value)
