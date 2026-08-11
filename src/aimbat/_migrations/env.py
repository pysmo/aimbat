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

    Alembic's default renderer already emits fully-qualified references for
    types outside SQLAlchemy's own builtins (e.g. `aimbat._types.SAPandasTimestamp`,
    `sqlmodel.sql.sqltypes.AutoString`), but only adds a matching import
    statement for its own `sqlalchemy.dialects.*` types — leaving generated
    migrations with undefined names for everything else. Always returning
    `False` keeps Alembic's default rendering; only the import is injected here.
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


def do_run_migrations(connection: Connection) -> None:
    """Configure and run migrations against an already-open connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite has very limited native ALTER TABLE support, so Alembic
        # rebuilds the table under the hood for column/constraint changes on
        # that dialect. Keying this off the live connection (rather than
        # hardcoding True) keeps a future non-SQLite backend from being
        # wrapped in that rebuild-the-table workaround unnecessarily.
        render_as_batch=connection.dialect.name == "sqlite",
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


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
