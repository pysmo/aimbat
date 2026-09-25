"""Unit tests for when AIMBAT configures logging, and what it leaves alone.

Each test runs in a subprocess: the test session itself calls
`configure_logging()` from an autouse fixture, so an in-process check could
never see the state a fresh import starts from.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOST_SETUP = """
from loguru import logger

records = []
logger.remove()
logger.add(records.append, level="DEBUG")
"""

_USE_AIMBAT = """
from sqlmodel import create_engine

from aimbat.core import create_project

create_project(create_engine("sqlite://"))
"""


def _run(code: str, cwd: Path) -> str:
    """Run `code` in a subprocess whose working directory is `cwd`."""
    # An inherited AIMBAT_LOGFILE would send the log somewhere this test
    # doesn't look; `cwd` has no `.env`, so the defaults apply.
    env = {k: v for k, v in os.environ.items() if not k.startswith("AIMBAT_")}
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=cwd, capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_import_leaves_the_host_logging_alone(tmp_path: Path) -> None:
    """Importing and using AIMBAT must not touch a host application's handlers.

    Regression test: `configure_logging()` used to run at import, and it
    starts with `logger.remove()`, which drops every handler loguru holds -
    not just AIMBAT's. Importing anything under `aimbat` therefore deleted
    the logging setup of whatever application had imported it.
    """
    output = _run(
        _HOST_SETUP
        + _USE_AIMBAT
        + """
logger.info("from the host")
print(any("from the host" in str(r) for r in records))
""",
        tmp_path,
    )
    assert output.strip() == "True", "The host's own handler should still be there"


def test_import_writes_no_log_file(tmp_path: Path) -> None:
    """Importing AIMBAT must not create `aimbat.log` in the current directory."""
    _run(_USE_AIMBAT, tmp_path)
    assert not (tmp_path / "aimbat.log").exists(), (
        "A library import should open no log file"
    )


def test_aimbat_records_are_silent_until_asked_for(tmp_path: Path) -> None:
    """AIMBAT emits nothing into a host's handlers until it is enabled.

    The host's own sink is used on both sides of the `enable` call, so this
    fails either way round: if AIMBAT logs before being asked to, and if
    enabling it does not actually reach the host's handler.
    """
    output = _run(
        _HOST_SETUP
        + _USE_AIMBAT
        + """
print(any("Creating new project" in str(r) for r in records))
logger.enable("aimbat")
"""
        + _USE_AIMBAT
        + """
print(any("Creating new project" in str(r) for r in records))
""",
        tmp_path,
    )
    assert output.split() == ["False", "True"], (
        "AIMBAT should be disabled on import, and enabled on request"
    )


@pytest.mark.parametrize(
    "entrypoint",
    [
        "from aimbat.logger import configure_logging; configure_logging()",
        "import sys; sys.argv = ['aimbat', '--help']\n"
        + "from aimbat.app import main\n"
        + "try:\n    main()\nexcept SystemExit:\n    pass",
    ],
    ids=["configure_logging", "cli_main"],
)
def test_logging_starts_once_asked_for(entrypoint: str, tmp_path: Path) -> None:
    """Both an explicit call and the CLI entrypoint open the log file.

    Args:
        entrypoint: Source that should end with logging configured.
        tmp_path: Working directory the log file is expected in.
    """
    _run(entrypoint + "\n" + _USE_AIMBAT, tmp_path)
    log = tmp_path / "aimbat.log"
    assert log.exists(), "Configuring logging should open the log file"
    assert "Creating new project" in log.read_text(), (
        "AIMBAT's records should reach the log file once configured"
    )
