"""Functional tests for the AIMBAT sampledata CLI commands.

All commands are invoked in-process via ``app()`` with
``aimbat.settings.sampledata_dir`` monkeypatched to a temporary directory.
A retry helper re-attempts the download up to 3 times to tolerate transient
network issues.
"""

from collections.abc import Callable
from pathlib import Path

import pytest

import aimbat._config as _config

_MAX_RETRIES = 3


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def sampledata_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Patches ``aimbat.settings.sampledata_dir`` to a temporary directory.

    Args:
        tmp_path: The pytest tmp_path fixture.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        Path to the temporary sample data directory.
    """
    target = tmp_path / "sample-data"
    monkeypatch.setattr(_config.settings, "sampledata_dir", target)
    return target


def _run_with_retries(
    cli: Callable[[str], None],
    command: str,
    retries: int = _MAX_RETRIES,
) -> None:
    """Runs a CLI command, retrying up to ``retries`` times on failure.

    Args:
        cli: The in-process CLI callable.
        command: The command string to run.
        retries: Maximum number of attempts.

    Raises:
        Exception: If all attempts fail.
    """
    last_exc: Exception | None = None
    for _ in range(retries):
        try:
            cli(command)
            return
        except Exception as exc:
            last_exc = exc
    raise last_exc  # type: ignore[misc]


# ===================================================================
# Download
# ===================================================================


@pytest.mark.slow
class TestSampledataDownload:
    """Tests for ``utils sampledata download``."""

    def test_download_creates_files(
        self,
        sampledata_dir: Path,
        cli: Callable[[str], None],
    ) -> None:
        """Verifies that download creates files inside the sampledata directory.

        Args:
            sampledata_dir: Path to the temporary sample data directory.
            cli: The in-process CLI callable.
        """
        _run_with_retries(cli, "utils sampledata download")
        assert sampledata_dir.exists(), (
            "Sample data directory should exist after download"
        )
        assert any(sampledata_dir.rglob("*")), (
            "Sample data directory should contain at least one file after download"
        )

    def test_download_creates_seismogram_files(
        self,
        sampledata_dir: Path,
        cli: Callable[[str], None],
    ) -> None:
        """Verifies that the download includes BHZ seismogram data files.

        Args:
            sampledata_dir: Path to the temporary sample data directory.
            cli: The in-process CLI callable.
        """
        _run_with_retries(cli, "utils sampledata download")
        bhz_files = list(sampledata_dir.rglob("*BHZ"))
        assert len(bhz_files) > 0, (
            "Expected at least one BHZ seismogram file in the downloaded sample data"
        )

    def test_download_twice_fails_without_force(
        self,
        sampledata_dir: Path,
        cli: Callable[[str], None],
    ) -> None:
        """Verifies that a second download without --force raises FileExistsError.

        Args:
            sampledata_dir: Path to the temporary sample data directory.
            cli: The in-process CLI callable.
        """
        _run_with_retries(cli, "utils sampledata download")
        assert sampledata_dir.exists(), "Directory should exist after first download"

        with pytest.raises((SystemExit, FileExistsError)):
            cli("utils sampledata download")

    def test_download_force_overwrites(
        self,
        sampledata_dir: Path,
        cli: Callable[[str], None],
    ) -> None:
        """Verifies that --force re-downloads and replaces existing sample data.

        Args:
            sampledata_dir: Path to the temporary sample data directory.
            cli: The in-process CLI callable.
        """
        _run_with_retries(cli, "utils sampledata download")
        assert sampledata_dir.exists(), "Directory should exist after first download"

        _run_with_retries(cli, "utils sampledata download --force")
        assert sampledata_dir.exists(), (
            "Directory should still exist after force re-download"
        )
        assert any(sampledata_dir.rglob("*")), (
            "Directory should contain files after force re-download"
        )


# ===================================================================
# Delete
# ===================================================================


@pytest.mark.slow
class TestSampledataDelete:
    """Tests for ``utils sampledata delete``."""

    def test_delete_removes_directory(
        self,
        sampledata_dir: Path,
        cli: Callable[[str], None],
    ) -> None:
        """Verifies that the sample data directory is removed after delete.

        Args:
            sampledata_dir: Path to the temporary sample data directory.
            cli: The in-process CLI callable.
        """
        _run_with_retries(cli, "utils sampledata download")
        assert sampledata_dir.exists(), "Directory should exist before delete"

        cli("utils sampledata delete")
        assert not sampledata_dir.exists(), (
            "Sample data directory should be absent after delete"
        )

    def test_download_after_delete_succeeds(
        self,
        sampledata_dir: Path,
        cli: Callable[[str], None],
    ) -> None:
        """Verifies that sample data can be re-downloaded after deletion.

        Args:
            sampledata_dir: Path to the temporary sample data directory.
            cli: The in-process CLI callable.
        """
        _run_with_retries(cli, "utils sampledata download")
        cli("utils sampledata delete")
        assert not sampledata_dir.exists(), "Directory should be absent after delete"

        _run_with_retries(cli, "utils sampledata download")
        assert sampledata_dir.exists(), "Directory should exist after re-downloading"
