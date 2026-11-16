"""Alembic migration support for AIMBAT project databases.

See the module docstring in `aimbat._migrations.env` for how the target
database connection is resolved.
"""

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import Connection, Engine

from aimbat.logger import logger

if TYPE_CHECKING:
    from alembic.config import Config

__all__ = [
    "SchemaMismatchError",
    "SchemaStaleWarning",
    "get_current_revision",
    "get_head_revision",
    "stamp_head",
    "upgrade_project",
]


class SchemaMismatchError(RuntimeError):
    """A database is not at a schema version that this installation can upgrade."""


_RECREATE = (
    "It cannot be upgraded. Move the project file out of the way, create a "
    + "new project with `aimbat project create` and add the data again."
)


def _unrecognised_revision_message(revision: str) -> str:
    return (
        f"This project's database is stamped at schema version '{revision}', "
        + "which this AIMBAT installation doesn't recognise. It was created by "
        + "an AIMBAT version from before the current project format, or by a "
        + f"newer one. {_RECREATE}"
    )


_UNSTAMPED_MESSAGE = (
    "This project's database has no schema version, so it predates the "
    + f"current AIMBAT project format. {_RECREATE}"
)


class SchemaStaleWarning(UserWarning):
    """A project database's schema is behind the latest Alembic revision.

    Raised via `warnings.warn()` rather than printed directly, so that
    library users can react to it programmatically - e.g. promote it to a
    hard error with `warnings.simplefilter("error", SchemaStaleWarning)` -
    without AIMBAT itself having to decide whether a stale schema should
    block execution. For CLI/subprocess scripting, use the
    `AIMBAT_STRICT_SCHEMA_CHECK` setting instead: `PYTHONWARNINGS`/`-W` do
    *not* reliably work for custom warning categories like this one, since
    Python resolves dotted category paths very early during interpreter
    startup, before the `aimbat` package is reliably importable (see
    `aimbat.db`'s module docstring).

    Attributes:
        current_revision: The revision the database is stamped at, or `None`
            for a database with no version history at all.
        head_revision: The latest revision available in AIMBAT's migration
            scripts.
        upgradeable: Whether `aimbat db upgrade` can bring the database up
            to date.
    """

    def __init__(
        self,
        message: str,
        current_revision: str | None,
        head_revision: str | None,
        upgradeable: bool,
    ) -> None:
        super().__init__(message)
        self.current_revision = current_revision
        self.head_revision = head_revision
        self.upgradeable = upgradeable


def _known_ancestors_of_head() -> set[str]:
    """All revision IDs that are ancestors of head, including head itself.

    Distinguishes a stale but upgradeable database from one stamped at a
    revision this installation doesn't know about - created before the
    current project format, by a newer AIMBAT release, or with a corrupted
    `alembic_version` value. `aimbat db upgrade` can only resolve the
    former.
    """
    from alembic.script import ScriptDirectory

    script_dir = ScriptDirectory(str(_migrations_dir()))
    return {
        revision.revision
        for revision in script_dir.walk_revisions(base="base", head="head")
    }


def _build_staleness_warning(current_revision: str | None) -> SchemaStaleWarning | None:
    """Build a `SchemaStaleWarning` for `current_revision`, or `None` if up to date.

    Shared by `aimbat.db`'s `first_connect` listener and the TUI's own
    toast-based equivalent (`_tui.app.AimbatTUI._warn_if_schema_stale`) so
    the two can't drift apart - they differ only in *how* they obtain
    `current_revision` (a raw cursor query for reentrancy-safety reasons in
    `db.py`'s case, `get_current_revision(engine)` in the TUI's).

    Args:
        current_revision: The revision the database is currently stamped
            at, or `None` for a database with no version history at all.

    Returns:
        A `SchemaStaleWarning` describing the mismatch, or `None` if
        `current_revision` already matches head.
    """
    head_revision = get_head_revision()
    if current_revision == head_revision:
        return None

    upgradeable = False
    if current_revision is None:
        message = _UNSTAMPED_MESSAGE
    elif current_revision not in _known_ancestors_of_head():
        message = _unrecognised_revision_message(current_revision)
    else:
        upgradeable = True
        message = (
            f"This project's database schema is out of date (at {current_revision}"
            + f", latest is {head_revision}); run `aimbat db upgrade`."
        )
    logger.warning(message)
    return SchemaStaleWarning(message, current_revision, head_revision, upgradeable)


def _migrations_dir() -> Path:
    """Path to the installed `aimbat._migrations` package.

    Deliberately not read from `alembic.ini` on disk (that file is a
    developer convenience for `uv run alembic ...` from a git checkout).
    Resolving it via the installed package instead means everything in this
    module also works for a `pip`/`uv tool install`ed AIMBAT with no
    checkout on disk.
    """
    import aimbat._migrations

    return Path(aimbat._migrations.__file__).parent


def _alembic_config(bind: Engine | Connection) -> "Config":
    """Build an Alembic `Config` bound to `bind`.

    `config.attributes["connection"]` is the standard Alembic "connection
    sharing" pattern (see `aimbat._migrations.env`): it makes `env.py`
    operate on exactly this engine rather than re-deriving its own from
    `aimbat.db.engine`, which matters for tests that use a different engine.
    Passing an open `Connection` instead of an `Engine` keeps Alembic inside
    a transaction the caller owns.
    """
    from alembic.config import Config

    import aimbat.models  # noqa: F401 - ensure SQLModel metadata is registered

    config = Config()
    config.set_main_option("script_location", str(_migrations_dir()))
    config.attributes["connection"] = bind
    return config


def get_current_revision(engine: Engine) -> str | None:
    """Return the Alembic revision `engine`'s database is stamped at.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.

    Returns:
        The current revision ID, or `None` if the database has never been
        stamped (e.g. one that doesn't exist yet).
    """
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        heads = migration_context.get_current_heads()
    return heads[0] if heads else None


def get_head_revision() -> str | None:
    """Return the latest revision ID available in AIMBAT's migration scripts.

    Reads `_migrations/versions/` on disk only, so it needs no database
    connection and is safe to call from contexts where opening one would
    be unsafe (e.g. from inside a SQLAlchemy `connect` event, before the
    connection being established has been returned to the pool).

    Returns:
        The head revision ID. `None` only if there are no migrations at all.
    """
    from alembic.script import ScriptDirectory

    script_dir = ScriptDirectory(str(_migrations_dir()))
    return script_dir.get_current_head()


def stamp_head(bind: Engine | Connection) -> None:
    """Mark a database as being at the latest Alembic revision.

    Writes Alembic's bookkeeping only, and runs no migration DDL. Intended for
    a database whose schema is already known to match `head`, e.g.
    immediately after `create_project()` creates a brand new one via
    `SQLModel.metadata.create_all()` rather than via a migration.

    Args:
        bind: Engine connected to the target database, or an open connection
            to it - the latter so the stamp can share a transaction with the
            schema it describes.
    """
    from alembic import command

    command.stamp(_alembic_config(bind), "head")


def _checkpoint_wal(engine: Engine) -> None:
    """Fold the write-ahead log back into the main database file.

    Without this, a copy of the database file alone is only as complete as
    the last checkpoint, and the `-wal` file has to be copied with it to stay
    recoverable - two files captured at two different instants.
    """
    with engine.connect() as connection:
        result = connection.exec_driver_sql(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).one_or_none()
    # (busy, wal_pages, checkpointed_pages); busy=1 means readers or writers
    # held it open and some of the log is still outstanding.
    if result is not None and result[0]:
        logger.warning(
            "Could not fully checkpoint the write-ahead log before backing up; "
            + "the backup's `-wal` sidecar is needed to restore it."
        )


def _unused_backup_path(db_path: Path, label: str) -> Path:
    """Return a `<db>.pre-<label>.bak` path that no file occupies yet.

    Retrying a failed upgrade takes a second backup at the same revision, so
    the revision alone doesn't identify one - and overwriting is at its worst
    exactly then, with the first backup the only intact copy left.
    """
    candidate = db_path.with_name(f"{db_path.name}.pre-{label}.bak")
    attempt = 1
    while candidate.exists():
        candidate = db_path.with_name(f"{db_path.name}.pre-{label}.{attempt}.bak")
        attempt += 1
    return candidate


def _backup_before_upgrade(engine: Engine, from_revision: str | None) -> None:
    """Copy a file-backed SQLite database aside before running migrations.

    A mid-chain migration failure (disk full, power loss, a bug in a future
    migration script) can leave a half-applied schema with no recovery path,
    so a copy is made first. No-op for `:memory:` databases, non-SQLite
    backends, or a database file that doesn't exist yet.

    The write-ahead log is checkpointed first, and an existing backup is never
    overwritten. The `-shm` file is not copied: it is rebuildable shared
    memory, not durable data.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.
        from_revision: The revision the backup is taken at, used only to
            label the backup filename.
    """
    if engine.url.get_backend_name() != "sqlite":
        return
    database = engine.url.database
    if not database or database == ":memory:":
        return
    db_path = Path(database)
    if not db_path.exists():
        return

    _checkpoint_wal(engine)

    backup_path = _unused_backup_path(db_path, from_revision or "unstamped")
    shutil.copy2(db_path, backup_path)
    wal = db_path.with_name(db_path.name + "-wal")
    if wal.exists() and wal.stat().st_size > 0:
        shutil.copy2(wal, backup_path.with_name(backup_path.name + "-wal"))
    logger.info(f"Backed up project database to {backup_path} before upgrading.")


def upgrade_project(engine: Engine) -> None:
    """Upgrade the project database to the latest Alembic revision.

    - A database stamped at a known ancestor of `head` (or `head` itself)
      has any pending migrations run.
    - A database with no schema at all is built by running the full
      migration chain.
    - Anything else is refused: a database stamped at a revision this
      installation doesn't recognise, or one that has tables but no version
      history. Neither can be brought to `head` by the migration scripts.

    A file-backed database is copied aside before any migration runs.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.

    Raises:
        SchemaMismatchError: If the database is stamped at an unrecognised
            revision, or has a schema but no version history.
    """
    from alembic import command
    from sqlalchemy import inspect

    config = _alembic_config(engine)
    current_revision = get_current_revision(engine)

    if current_revision is None:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                raise SchemaMismatchError(_UNSTAMPED_MESSAGE)
    elif current_revision not in _known_ancestors_of_head():
        raise SchemaMismatchError(_unrecognised_revision_message(current_revision))

    _backup_before_upgrade(engine, current_revision)
    command.upgrade(config, "head")
