"""Database engine for the AIMBAT project file.

The engine is created from `Settings.db_url` (see `aimbat._config`), which
defaults to a SQLite database at `aimbat.db` in the current working directory.
The path can be overridden via environment variable or `.env` file:

```bash
AIMBAT_PROJECT=/path/to/project.db  # derives db_url automatically
AIMBAT_DB_URL=sqlite+pysqlite:///absolute/path/to/project.db  # explicit override
```

For SQLite connections, `PRAGMA foreign_keys=ON` is set automatically on every
new connection to enforce referential integrity.
"""

import sqlite3

from sqlalchemy import event
from sqlalchemy.pool import ConnectionPoolEntry
from sqlmodel import create_engine

from aimbat import settings

__all__ = ["engine"]

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


# Automatically enforce foreign keys for every new connection if using SQLite
if engine.name == "sqlite":

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(
        dbapi_connection: sqlite3.Connection, connection_record: ConnectionPoolEntry
    ) -> None:
        """Enable foreign key and WAL support for each new SQLite connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
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
