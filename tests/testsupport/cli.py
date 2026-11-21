"""Helpers for running commands and reading their output."""

import json
import os
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from aimbat.app import app

__all__ = ["LOG_DIR", "error_text", "exit_code", "project_dump", "worker_logfile"]

#: Gitignored directory for the log files of a test session.
LOG_DIR = Path(__file__).parents[1] / ".logs"

# Rich draws panel borders with one of these, depending on the terminal:
# rounded or square on a Unicode console, ASCII on a legacy encoding.
_VERTICAL = "│┃║|"
_CORNERS = "╭╮╰╯┌┐└┘┏┓┗┛╔╗╚╝+"
_HORIZONTAL = "─━═-"


def exit_code(command: str | list[str]) -> int:
    """Run an `aimbat` command in-process and return its exit code."""
    with pytest.raises(SystemExit) as exc_info:
        app(command)
    code = exc_info.value.code
    return code if isinstance(code, int) else 0


def error_text(captured: str) -> str:
    """Return printed text with panel borders removed and whitespace collapsed.

    Line endings, wrapping and the box style differ between platforms. The
    result is one line, with words separated by single spaces, so a test can
    check for a phrase with `in`.
    """
    words: list[str] = []
    for line in captured.splitlines():
        line = line.strip()
        if line[:1] in _CORNERS and line[1:2] in _HORIZONTAL:
            # A top or bottom border, possibly with a title.
            line = line.strip(_CORNERS + _HORIZONTAL + " ")
        else:
            if line[:1] in _VERTICAL:
                line = line[1:]
            if line[-1:] in _VERTICAL:
                line = line[:-1]
        words += line.split()
    return " ".join(words)


def project_dump(
    run: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    command: Sequence[str],
) -> Any:
    """Run a dump command with `run` and return its parsed JSON output.

    Args:
        run: Runs `aimbat` with the given arguments, such as the
            `aimbat_subprocess` fixture.
        command: Arguments of the dump command, such as `["event", "dump"]`.

    Raises:
        AssertionError: The command exited with a non-zero code.
    """
    result = run(command)
    if result.returncode != 0:
        raise AssertionError(
            f"`aimbat {' '.join(command)}` exited with {result.returncode}:\n"
            f"{result.stderr}"
        )
    return json.loads(result.stdout)


def worker_logfile() -> str:
    """Return a log file path in `LOG_DIR`, unique per xdist worker.

    Under `pytest-xdist` every worker runs in its own process but shares the
    working directory, so a fixed name would have all workers appending to one
    file. `PYTEST_XDIST_WORKER` is unset on a non-parallel run (`"master"`).
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    LOG_DIR.mkdir(exist_ok=True)
    return str(LOG_DIR / f"aimbat_test_{worker}.log")
