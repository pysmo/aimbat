"""Functional tests for AIMBAT db CLI commands that require a real file.

These tests are run via subprocess so that Alembic operates on an actual
database file rather than an in-memory database.
"""

import os
import sqlite3
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest


@pytest.mark.slow
@pytest.mark.cli
class TestDbCommands:
    """Tests for `aimbat db upgrade`/`aimbat db current` against a real file."""

    def test_current_fails_when_no_project(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    ) -> None:
        """Verifies `db current` fails with a friendly error when there is no project."""
        result = aimbat_subprocess(["db", "current"])
        assert result.returncode != 0
        assert "No AIMBAT project found" in result.stderr

    def test_upgrade_fails_when_no_project(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    ) -> None:
        """Verifies `db upgrade` fails with a friendly error when there is no project."""
        result = aimbat_subprocess(["db", "upgrade"])
        assert result.returncode != 0
        assert "No AIMBAT project found" in result.stderr

    def test_current_shows_no_history_before_stamping(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    ) -> None:
        """A freshly created project is stamped immediately, so `db current`
        should already report a revision rather than "no history".
        """
        aimbat_subprocess(["project", "create"])
        result = aimbat_subprocess(["db", "current"])
        assert result.returncode == 0, result.stderr
        assert "No Alembic version history" not in result.stdout

    def test_upgrade_on_fresh_project_is_a_no_op(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    ) -> None:
        """Verifies `db upgrade` succeeds cleanly on an already up-to-date project."""
        aimbat_subprocess(["project", "create"])
        result = aimbat_subprocess(["db", "upgrade"])
        assert result.returncode == 0, result.stderr

    def test_upgrade_then_current_reports_same_revision(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    ) -> None:
        """Verifies the revision reported by `db current` is stable across an upgrade."""
        aimbat_subprocess(["project", "create"])
        before = aimbat_subprocess(["db", "current"])
        aimbat_subprocess(["db", "upgrade"])
        after = aimbat_subprocess(["db", "current"])
        assert before.stdout == after.stdout

    def test_missing_unrelated_table_is_not_reported_as_no_project(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        db_path: Path,
    ) -> None:
        """A missing table other than `aimbatevent` must not be reported as "no project".

        Regression test: the `handle_error` listener in `db.py` previously
        matched any "no such table" error, which produced a misleading "No
        AIMBAT project found" message for a project whose schema is present
        but broken in some other way.
        """
        aimbat_subprocess(["project", "create"])
        with sqlite3.connect(db_path) as connection:
            connection.execute("DROP TABLE aimbatstation")

        result = aimbat_subprocess(["station", "list"])
        assert result.returncode != 0
        assert "No AIMBAT project found" not in result.stderr


@pytest.mark.slow
@pytest.mark.cli
class TestSchemaStalenessWarning:
    """Tests for the staleness check every CLI command performs. Unlike the
    underlying `aimbat.db` warning (advisory by default - see its module
    docstring), `handle_issues` unconditionally promotes it to a hard
    failure for AIMBAT's own CLI, so every command either fully succeeds or
    cleanly fails with the same attributable message - never silently
    continues, and never crashes later with a raw, unrelated
    `sqlalchemy.exc.OperationalError` from whatever query happens to first
    touch a drifted column. Each `aimbat_subprocess` call is a fresh
    process, so the check (fired once via `first_connect`) is exercised
    independently by each command below.
    """

    def test_silent_when_up_to_date(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    ) -> None:
        """A freshly created (and therefore immediately-stamped) project
        should never trigger the warning.
        """
        aimbat_subprocess(["project", "create"])
        result = aimbat_subprocess(["db", "current"])
        assert "run `aimbat db upgrade`" not in result.stderr

    def test_warns_on_legacy_unstamped_database(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        db_path: Path,
    ) -> None:
        """A pre-Alembic database (no `alembic_version` table at all) should
        trigger the "predates schema versioning" warning on any command.
        """
        aimbat_subprocess(["project", "create"])
        with sqlite3.connect(db_path) as connection:
            connection.execute("DROP TABLE alembic_version")

        result = aimbat_subprocess(["db", "current"])

        assert result.returncode != 0
        assert "predates AIMBAT's schema versioning" in result.stderr
        assert "run `aimbat db upgrade`" in result.stderr

    def test_db_upgrade_does_not_warn_about_itself(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        db_path: Path,
    ) -> None:
        """`aimbat db upgrade` on a stale database must not print "run
        `aimbat db upgrade`" - that's the exact command already running.
        """
        aimbat_subprocess(["project", "create"])
        with sqlite3.connect(db_path) as connection:
            connection.execute("DROP TABLE alembic_version")

        result = aimbat_subprocess(["db", "upgrade"])

        assert result.returncode == 0, result.stderr
        assert "run `aimbat db upgrade`" not in result.stderr

    def test_warns_on_unrecognised_revision(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        db_path: Path,
    ) -> None:
        """A database stamped at a revision this installation doesn't
        recognise at all (e.g. a different/newer AIMBAT release, or a
        corrupted `alembic_version` value) must get a distinct warning that
        does *not* tell the user to run `aimbat db upgrade` - that command
        can't resolve an unknown revision and would just fail. This is
        different from "genuinely behind a known revision", which isn't
        constructible with only one migration in existence; see
        `tests/integration/core/test_migrations.py` for that case, tested
        directly against `_build_staleness_warning`.
        """
        aimbat_subprocess(["project", "create"])
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                "UPDATE alembic_version SET version_num = 'not_a_real_revision'"
            )

        result = aimbat_subprocess(["db", "current"])

        assert result.returncode != 0
        assert "doesn't recognise" in result.stderr
        assert "not_a_real_revision" in result.stderr
        assert "run `aimbat db upgrade`" not in result.stderr

    def test_upgrade_fails_cleanly_on_unrecognised_revision(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        db_path: Path,
    ) -> None:
        """`aimbat db upgrade` against an unrecognised revision must fail
        with a friendly, actionable error - not a raw Alembic "Can't locate
        revision" exception leaking straight to the user.
        """
        aimbat_subprocess(["project", "create"])
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                "UPDATE alembic_version SET version_num = 'not_a_real_revision'"
            )

        result = aimbat_subprocess(["db", "upgrade"])

        assert result.returncode != 0
        assert "doesn't recognise" in result.stderr
        assert "Can't locate revision" not in result.stderr

    def test_no_warning_when_no_project_exists(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
    ) -> None:
        """No project at all should surface only the existing "run aimbat
        project create" error, not a staleness warning about it.
        """
        result = aimbat_subprocess(["db", "current"])
        assert "run `aimbat db upgrade`" not in result.stderr


@pytest.mark.slow
@pytest.mark.cli
class TestStrictSchemaCheck:
    """Tests for `AIMBAT_STRICT_SCHEMA_CHECK`.

    AIMBAT's own CLI (see `TestSchemaStalenessWarning` above) and TUI always
    treat a stale schema as a hard failure now, regardless of this setting -
    so it no longer has any observable effect on `aimbat` commands. Its
    remaining, narrower purpose is third-party code using `aimbat.db.engine`
    directly (bypassing AIMBAT's CLI/TUI entirely), which is what the tests
    below exercise. Exists because `PYTHONWARNINGS`/`-W` don't reliably work
    for third-party warning categories (Python resolves them too early
    during interpreter startup), so this setting sidesteps that by calling
    `warnings.simplefilter` programmatically instead of relying on
    env-var-driven filter parsing.
    """

    def test_still_succeeds_when_strict_and_up_to_date(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Strict mode doesn't affect an already up-to-date project."""
        aimbat_subprocess(["project", "create"])

        monkeypatch.setenv("AIMBAT_STRICT_SCHEMA_CHECK", "true")
        result = aimbat_subprocess(["db", "current"])

        assert result.returncode == 0, result.stderr

    def test_stale_warning_still_raises_only_once_per_process(
        self,
        aimbat_subprocess: Callable[[Sequence[str]], subprocess.CompletedProcess[str]],
        db_path: Path,
    ) -> None:
        """SQLAlchemy's `first_connect` is only marked complete if its
        listener returns without raising - since strict mode makes it raise
        deliberately, relying on `first_connect` alone would mean it fires
        again on every subsequent *new* physical connection within the same
        process, not just once. This matters less for AIMBAT's own CLI/TUI
        (both exit on the first occurrence regardless) than for a
        third-party script built directly on `aimbat.db.engine` that catches
        the exception and keeps running - exactly what this test does:
        opens the real `aimbat.db.engine` directly (bypassing the CLI) to
        exercise several new connections within one process and confirm
        only the first raises.
        """
        aimbat_subprocess(["project", "create"])
        with sqlite3.connect(db_path) as connection:
            connection.execute("DROP TABLE alembic_version")

        env = os.environ.copy()
        env["AIMBAT_DB_URL"] = f"sqlite+pysqlite:///{db_path}"
        env["AIMBAT_STRICT_SCHEMA_CHECK"] = "true"
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                (
                    "from aimbat.db import engine\n"
                    "raised = []\n"
                    "for _ in range(3):\n"
                    "    try:\n"
                    "        with engine.connect():\n"
                    "            pass\n"
                    "    except Exception as e:\n"
                    "        raised.append(type(e).__name__)\n"
                    "print(len(raised))\n"
                ),
            ],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "1", (
            f"expected exactly 1 raise across 3 new connections, "
            f"got stdout={result.stdout!r} stderr={result.stderr!r}"
        )
