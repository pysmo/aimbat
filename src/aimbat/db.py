"""Database engine for the AIMBAT project file.

The engine is created from `Settings.db_url` (see `aimbat._config`), which
defaults to a SQLite database at `aimbat.db` in the current working directory.
The path can be overridden via environment variable or `.env` file:

```bash
AIMBAT_PROJECT=/path/to/project.db  # derives db_url automatically
AIMBAT_DB_URL=sqlite+pysqlite:///absolute/path/to/project.db  # explicit override
```

For SQLite connections, `PRAGMA foreign_keys=ON` is set automatically on every
new connection to enforce referential integrity. If the project's schema is
out of date, a one-time `aimbat.core.SchemaStaleWarning` is raised suggesting
`aimbat db upgrade`; nothing is changed automatically. The same message is
also logged at `WARNING` level (see `aimbat.logger`), so it's still visible
in `aimbat.log` even if the on-screen message is missed or scrolls past.
Being a real Python warning rather than a plain print, third-party
code using this module's `engine` directly can turn it into a hard error
(`warnings.simplefilter("error", SchemaStaleWarning)`, or set
`AIMBAT_STRICT_SCHEMA_CHECK=true`) without AIMBAT having to decide that
policy for them. Note that `PYTHONWARNINGS`/`-W` do *not* reliably work for
this — Python resolves dotted warning categories very early during
interpreter startup, before the `aimbat` package is reliably importable;
`AIMBAT_STRICT_SCHEMA_CHECK` exists specifically to sidestep that.

AIMBAT's own CLI and TUI don't rely on this advisory default at all: both
unconditionally promote `SchemaStaleWarning` to a hard failure regardless of
`AIMBAT_STRICT_SCHEMA_CHECK` - `aimbat._cli.common.handle_issues` for the
CLI (reported through the same red-panel error path as any other failure),
and `aimbat._tui.app.AimbatTUI.on_mount` for the TUI (a blocking modal
instead of the main UI). `AIMBAT_STRICT_SCHEMA_CHECK` is only meaningful for
third-party code that imports `engine` from this module directly and never
goes through AIMBAT's own entry points.
"""

import sqlite3
import warnings

from sqlalchemy import event
from sqlalchemy.pool import ConnectionPoolEntry
from sqlmodel import create_engine

from aimbat import settings
from aimbat.core._migrations import SchemaStaleWarning
from aimbat.logger import logger

__all__ = ["engine"]

if settings.strict_schema_check:
    warnings.simplefilter("error", SchemaStaleWarning)

logger.debug(f"Initialising AIMBAT database engine with {settings.db_url=}.")

engine = create_engine(
    url=settings.db_url,
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    }
    if "sqlite" in settings.db_url
    else {},
)
"""AIMBAT database engine."""


_SQLITE_PRAGMAS = [
    "PRAGMA foreign_keys=ON",
    "PRAGMA journal_mode=WAL",
]


# Automatically enforce foreign keys for every new connection if using SQLite
if engine.name == "sqlite":

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(
        dbapi_connection: sqlite3.Connection, connection_record: ConnectionPoolEntry
    ) -> None:
        """Enable specific PRAGMAs for each new SQLite connection."""
        logger.debug(
            f"Configuring SQLite connection with: {', '.join(_SQLITE_PRAGMAS)}."
        )
        cursor = dbapi_connection.cursor()
        for pragma in _SQLITE_PRAGMAS:
            cursor.execute(pragma)
        cursor.close()

    @event.listens_for(engine, "handle_error")
    def _handle_missing_schema(exception_context) -> None:  # type: ignore[no-untyped-def]
        """Convert 'no such table' errors to a user-friendly RuntimeError."""
        if not exception_context.is_disconnect and "no such table" in str(
            exception_context.original_exception
        ):
            raise RuntimeError(
                "No AIMBAT project found. Run: aimbat project create"
            ) from exception_context.original_exception

    _schema_staleness_checked = False

    @event.listens_for(engine, "first_connect")
    def _warn_if_schema_stale(
        dbapi_connection: sqlite3.Connection, connection_record: ConnectionPoolEntry
    ) -> None:
        """Raise `SchemaStaleWarning` if the project's schema is out of date.

        Fires at most once per process. This matters less for AIMBAT's own
        entry points than it might seem - the CLI exits on the first
        exception via `handle_issues`, and the TUI's `on_mount()` checks
        `_project_exists(engine)` before anything else touches the database,
        so it dies on that same first exception too, before any second
        connection could be attempted. Where it actually matters is a
        third-party script or service built directly on `aimbat.db.engine`
        (the pattern `SchemaStaleWarning`'s own docstring documents:
        `warnings.simplefilter("error", SchemaStaleWarning)`) that catches
        the exception and keeps running - plausibly for far longer, and with
        far more subsequent connections, than either of AIMBAT's own
        entry points ever do.

        Enforced with an explicit module-level flag, checked and set
        *before* the warning (which may raise, under
        `AIMBAT_STRICT_SCHEMA_CHECK`) is built: SQLAlchemy's `first_connect`
        is normally described as firing "only once per Engine", but that
        guarantee is implemented via `exec_once_unless_exception` - if the
        listener raises, it is *not* marked complete and fires again on the
        next new physical connection. Under strict mode this listener
        deliberately raises, so relying on `first_connect` alone would mean
        repeated warnings/errors from a single stale database across a
        process's lifetime instead of one.

        Uses the raw DBAPI connection directly rather than a SQLAlchemy
        `Connection`/`Engine`: this runs while the pool is still establishing
        its first connection, and re-entering the pool via `engine.connect()`
        from here would be unsafe.
        """
        global _schema_staleness_checked
        if _schema_staleness_checked:
            return
        _schema_staleness_checked = True

        cursor = dbapi_connection.cursor()
        try:
            no_project = (
                cursor.execute("PRAGMA table_info(aimbatevent)").fetchall() == []
            )
            if no_project:
                # No project at all - the handle_error listener above already
                # covers this with its own friendly message.
                return

            try:
                cursor.execute("SELECT version_num FROM alembic_version")
                row = cursor.fetchone()
                current_revision: str | None = row[0] if row else None
            except sqlite3.OperationalError:
                current_revision = None  # pre-Alembic database
        finally:
            cursor.close()

        from aimbat.core._migrations import _build_staleness_warning

        warning = _build_staleness_warning(current_revision)
        if warning is not None:
            warnings.warn(warning, stacklevel=1)
