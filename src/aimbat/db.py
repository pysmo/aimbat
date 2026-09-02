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
also logged at `WARNING` level (see `aimbat.logger`), so it remains visible in
`aimbat.log` even if the on-screen warning is missed.

Third-party code using this module's `engine` directly can promote the
warning to a hard error, either with
`warnings.simplefilter("error", SchemaStaleWarning)` or by setting
`AIMBAT_STRICT_SCHEMA_CHECK=true` (`PYTHONWARNINGS`/`-W` are not a reliable
way to do this for this warning category; use `AIMBAT_STRICT_SCHEMA_CHECK`
instead). AIMBAT's own CLI and TUI always treat a stale schema as a hard
failure regardless of `AIMBAT_STRICT_SCHEMA_CHECK` — that setting only
affects third-party code that imports `engine` from this module directly.
"""

import sqlite3
import threading
import warnings

from sqlalchemy import event
from sqlalchemy.engine.interfaces import ExceptionContext
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
        """Enable specific PRAGMAs for each new SQLite connection.

        Args:
            dbapi_connection: The raw DBAPI connection that was just opened.
            connection_record: The connection pool's record for the connection.
        """
        logger.debug(
            f"Configuring SQLite connection with: {', '.join(_SQLITE_PRAGMAS)}."
        )
        cursor = dbapi_connection.cursor()
        for pragma in _SQLITE_PRAGMAS:
            cursor.execute(pragma)
        cursor.close()

    @event.listens_for(engine, "handle_error")
    def _handle_missing_schema(exception_context: ExceptionContext) -> None:
        """Convert a missing `aimbatevent` table error to a user-friendly RuntimeError.

        Args:
            exception_context: SQLAlchemy's context for the error being handled.

        Raises:
            RuntimeError: If the original error indicates that no AIMBAT
                project exists at the configured database location.
        """
        if not exception_context.is_disconnect and "no such table: aimbatevent" in str(
            exception_context.original_exception
        ):
            raise RuntimeError(
                "No AIMBAT project found. Run: aimbat project create"
            ) from exception_context.original_exception

    _schema_staleness_checked = False
    _schema_staleness_lock = threading.Lock()

    @event.listens_for(engine, "first_connect")
    def _warn_if_schema_stale(
        dbapi_connection: sqlite3.Connection, connection_record: ConnectionPoolEntry
    ) -> None:
        """Warn if the project's schema is behind the latest Alembic revision.

        Checks at most once per process. Has no effect if no AIMBAT project
        exists yet at the configured database location.

        Args:
            dbapi_connection: The raw DBAPI connection that was just opened.
            connection_record: The connection pool's record for the connection.

        Raises:
            SchemaStaleWarning: If the schema is out of date. Raised as a
                warning via `warnings.warn`, which becomes a hard exception
                when `AIMBAT_STRICT_SCHEMA_CHECK` is enabled.
        """
        global _schema_staleness_checked
        # Hold the lock for the whole body, not just the flag flip: the check
        # must run exactly once even if this listener is ever re-registered on
        # `connect` (which fires per connection) instead of `first_connect`.
        with _schema_staleness_lock:
            if _schema_staleness_checked:
                return
            _schema_staleness_checked = True

            cursor = dbapi_connection.cursor()
            try:
                no_project = (
                    cursor.execute("PRAGMA table_info(aimbatevent)").fetchall() == []
                )
                if no_project:
                    # No project at all - the handle_error listener above
                    # already covers this with its own friendly message.
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
