"""Functional tests for AIMBAT project CLI commands that require a real file.

These tests are run via subprocess so that the engine lifecycle (create → delete)
operates on an actual database file rather than an in-memory database.
"""

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest


@pytest.mark.slow
@pytest.mark.cli
class TestProjectLifecycleWithFile:
    """Tests for project creation and deletion against a real database file."""

    def test_create_project(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        db_path: Path,
    ) -> None:
        """Verifies that a new project database file is created."""
        result = aimbat_subprocess(["project", "create"])
        assert result.returncode == 0, result.stderr
        assert db_path.exists(), "Database file should exist after project create"

    def test_create_project_twice_fails(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    ) -> None:
        """Verifies that creating a project when one already exists fails."""
        aimbat_subprocess(["project", "create"])
        result = aimbat_subprocess(["project", "create"])
        assert result.returncode != 0, "Second project create should fail"

    def test_project_info(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    ) -> None:
        """Verifies that project info displays a panel after creation."""
        aimbat_subprocess(["project", "create"])
        result = aimbat_subprocess(["project", "info"])
        assert result.returncode == 0, result.stderr
        assert "Project Info" in result.stdout, (
            "Output should contain the 'Project Info' panel title"
        )

    def test_project_info_shows_file_path(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        db_path: Path,
    ) -> None:
        """Verifies that project info includes the database file path."""
        aimbat_subprocess(["project", "create"])
        result = aimbat_subprocess(["project", "info"])
        assert db_path.name in result.stdout, (
            "Output should contain the database filename"
        )

    def test_delete_project(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        db_path: Path,
    ) -> None:
        """Verifies that the project database file is removed after deletion."""
        aimbat_subprocess(["project", "create"])
        result = aimbat_subprocess(["project", "delete"])
        assert result.returncode == 0, result.stderr
        assert not db_path.exists(), (
            "Database file should be absent after project delete"
        )
