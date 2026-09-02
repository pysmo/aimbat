"""Alembic environment script.

Unlike a typical Alembic setup, this does *not* read `sqlalchemy.url` from
`alembic.ini`. In 'online' mode it prefers an `Engine`/`Connection` passed in
via `config.attributes["connection"]` (the standard Alembic pattern for
connection sharing — see `aimbat.core._migrations._alembic_config`), falling
back to `aimbat.db.engine` when nothing is supplied (e.g. bare
`uv run alembic ...` on the command line). Either way the actual URL
ultimately traces back to `aimbat.settings.db_url`, so
`AIMBAT_DB_URL`/`AIMBAT_PROJECT`/`.env` keep working transparently for
migrations exactly as they do for every other AIMBAT command.
"""

from logging.config import fileConfig
from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy import Connection, Engine
from sqlmodel import SQLModel

# Import locally to ensure SQLModel registers all table metadata before
# `target_metadata` is read (mirrors the same defensive import in
# `aimbat.core._project.create_project`).
import aimbat.models  # noqa: F401
from aimbat import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def render_item(
    type_: str, obj: Any, autogen_context: AutogenContext
) -> str | Literal[False]:
    """Add missing imports for AIMBAT/SQLModel column types during autogenerate.

    Registered as Alembic's `render_item` hook. Ensures generated migration
    scripts import any `aimbat.*` or `sqlmodel.*` type referenced in a
    rendered column definition.

    Args:
        type_: Category of object being rendered (e.g. `"type"`).
        obj: The object being rendered.
        autogen_context: Autogenerate context, used here to register the
            required import.

    Returns:
        Always `False`, so that Alembic falls back to its default rendering
        for `obj`.
    """
    if type_ == "type":
        module = type(obj).__module__
        if module.split(".", 1)[0] in ("aimbat", "sqlmodel"):
            autogen_context.imports.add(f"import {module}")
    return False


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emits SQL, does not open a connection)."""
    context.configure(
        url=settings.db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=settings.db_url.startswith("sqlite"),
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def _set_sqlite_foreign_keys(connection: Connection, enabled: bool) -> None:
    """Toggle SQLite's `foreign_keys` pragma on the raw DBAPI connection.

    The pragma is a no-op while a transaction is open, so it must bypass
    SQLAlchemy's transaction management by going straight to the DBAPI cursor.
    """
    cursor = connection.connection.cursor()
    cursor.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")
    cursor.close()


def do_run_migrations(connection: Connection) -> None:
    """Configure and run migrations against an already-open connection.

    Args:
        connection: Database connection to run migrations against.
    """
    is_sqlite = connection.dialect.name == "sqlite"

    if is_sqlite:
        # Batch migrations rebuild a table by DROP + recreate. With foreign
        # key enforcement on (AIMBAT's engine sets `PRAGMA foreign_keys=ON`),
        # dropping a table that has `ON DELETE CASCADE` children - e.g.
        # `aimbatsnapshot` - deletes every child row. Disable enforcement for
        # the migration, and restore it afterwards so a pooled connection is
        # never handed back with FK checks off.
        _set_sqlite_foreign_keys(connection, False)

    try:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite has very limited native ALTER TABLE support, so Alembic
            # rebuilds the table under the hood for column/constraint changes
            # on that dialect. Keying this off the live connection (rather
            # than hardcoding True) keeps a future non-SQLite backend from
            # being wrapped in that rebuild-the-table workaround unnecessarily.
            render_as_batch=is_sqlite,
            render_item=render_item,
        )

        with context.begin_transaction():
            context.run_migrations()
    finally:
        if is_sqlite:
            _set_sqlite_foreign_keys(connection, True)


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Uses the `Engine`/`Connection` supplied via `config.attributes["connection"]`
    if present, otherwise falls back to AIMBAT's own database engine.
    """
    connectable = config.attributes.get("connection", None)

    if connectable is None:
        from aimbat.db import engine as connectable

    if isinstance(connectable, Connection):
        do_run_migrations(connectable)
    else:
        assert isinstance(connectable, Engine)
        with connectable.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
