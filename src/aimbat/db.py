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
from aimbat import settings
from sqlmodel import create_engine
from sqlalchemy import event
from sqlalchemy.pool import ConnectionPoolEntry

__all__ = ["engine"]

engine = create_engine(url=settings.db_url, echo=False)
"""AIMBAT database engine."""


# Automatically enforce foreign keys for every new connection if using SQLite
if engine.name == "sqlite":

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(
        dbapi_connection: sqlite3.Connection, connection_record: ConnectionPoolEntry
    ) -> None:
        """Enable foreign key support for each new SQLite connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
