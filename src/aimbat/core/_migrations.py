"""Alembic migration support for AIMBAT project databases.

See the module docstring in `aimbat._migrations.env` for how the target
database connection is resolved.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import Engine

from aimbat.logger import logger

if TYPE_CHECKING:
    from alembic.config import Config

__all__ = [
    "upgrade_project",
    "get_current_revision",
    "get_head_revision",
    "stamp_head",
    "SchemaMismatchError",
    "SchemaStaleWarning",
]


class SchemaMismatchError(RuntimeError):
    """An un-stamped database's live schema doesn't match a known revision."""


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
            for a pre-Alembic database with no version history at all.
        head_revision: The latest revision available in AIMBAT's migration
            scripts.
    """

    def __init__(
        self, message: str, current_revision: str | None, head_revision: str | None
    ) -> None:
        super().__init__(message)
        self.current_revision = current_revision
        self.head_revision = head_revision


def _known_ancestors_of_head() -> set[str]:
    """All revision IDs that are ancestors of head, including head itself.

    Distinguishes a genuinely stale (but recognisable, upgradeable) database
    from one stamped at a revision this installation doesn't know about at
    all - e.g. created by a different/newer AIMBAT release, or a corrupted
    `alembic_version` value. `aimbat db upgrade` can only resolve the
    former; attempting it against the latter fails with a raw Alembic
    "Can't locate revision identified by ..." error, and blindly telling a
    user to "run `aimbat db upgrade`" in that case is actively wrong advice.
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
            at, or `None` for a pre-Alembic database with no version
            history at all.

    Returns:
        A `SchemaStaleWarning` describing the mismatch, or `None` if
        `current_revision` already matches head.
    """
    head_revision = get_head_revision()
    if current_revision == head_revision:
        return None

    if (
        current_revision is not None
        and current_revision not in _known_ancestors_of_head()
    ):
        message = (
            f"This project's database is stamped at schema version "
            f"'{current_revision}', which this AIMBAT installation doesn't "
            "recognise - it may have been created by a different or newer "
            "AIMBAT release, or the version record may be corrupted. "
            "`aimbat db upgrade` cannot resolve this automatically; manual "
            "inspection is required."
        )
    elif current_revision is None:
        message = (
            "This project predates AIMBAT's schema versioning — run "
            "`aimbat db upgrade` once to bring it up to date."
        )
    else:
        message = (
            f"This project's database schema is out of date (at "
            f"{current_revision}, latest is {head_revision}) — run "
            "`aimbat db upgrade`."
        )
    logger.warning(message)
    return SchemaStaleWarning(message, current_revision, head_revision)


def _migrations_dir() -> Path:
    """Path to the installed `aimbat._migrations` package.

    Deliberately not read from `alembic.ini` on disk (that file is a
    developer convenience for `uv run alembic ...` from a git checkout) —
    resolving it via the installed package instead means everything in this
    module also works for a `pip`/`uv tool install`ed AIMBAT with no
    checkout on disk.
    """
    import aimbat._migrations

    return Path(aimbat._migrations.__file__).parent


def _alembic_config(engine: Engine) -> "Config":
    """Build an Alembic `Config` bound to `engine`.

    `config.attributes["connection"]` is the standard Alembic "connection
    sharing" pattern (see `aimbat._migrations.env`): it makes `env.py`
    operate on exactly this engine rather than re-deriving its own from
    `aimbat.db.engine`, which matters for tests that use a different engine.
    """
    from alembic.config import Config

    import aimbat.models  # noqa: F401 - ensure SQLModel metadata is registered

    config = Config()
    config.set_main_option("script_location", str(_migrations_dir()))
    config.attributes["connection"] = engine
    return config


def _find_matching_revision(engine: Engine) -> str | None:
    """Find which known revision (if any) `engine`'s live schema matches.

    Checked from `head` backwards to the baseline - closest-to-head match
    found first, since "already caught up except for the very latest
    migration" is the common case for a database that just skipped one
    release. For each candidate revision, a disposable in-memory database is
    built by replaying the migration chain up to that revision, then
    compared against `engine`'s live schema using Alembic's own comparator
    (the same one that powers `--autogenerate`) - fed a *reflected*
    `MetaData` rather than `SQLModel.metadata`, so the comparison isn't tied
    to the current models and works for any historical revision, not just
    head.

    Comparing only against `head`/`SQLModel.metadata` (an earlier version of
    this function) was wrong: a pre-Alembic database created before this
    revision-matching logic shipped, then never touched again while a
    *later* migration was added elsewhere, would have a schema matching the
    baseline exactly but not head - and would be rejected outright instead
    of being stamped at the baseline and upgraded the rest of the way.

    Like the rest of this module's schema-matching, this only sees what
    Alembic's comparator can see - not the hand-written triggers (see
    `core._project.create_project`), which are invisible to it regardless
    of what `MetaData` they're compared against. A live schema with correct
    tables/columns but an outdated trigger would still be reported as
    matching; that's an existing limitation carried over unchanged, not one
    this function introduces.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.

    Returns:
        The revision ID of the closest-to-head matching revision, or `None`
        if the live schema doesn't match any known revision.
    """
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import MetaData, create_engine

    script_dir = ScriptDirectory(str(_migrations_dir()))

    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)

        for script in script_dir.walk_revisions(base="base", head="head"):
            scratch_engine = create_engine("sqlite://")
            try:
                command.upgrade(_alembic_config(scratch_engine), script.revision)
                scratch_metadata = MetaData()
                scratch_metadata.reflect(bind=scratch_engine)
            finally:
                scratch_engine.dispose()

            if not compare_metadata(migration_context, scratch_metadata):
                return script.revision

    return None


def get_current_revision(engine: Engine) -> str | None:
    """Return the Alembic revision `engine`'s database is stamped at.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.

    Returns:
        The current revision ID, or `None` if the database has never been
        stamped (e.g. a pre-Alembic database, or one that doesn't exist yet).
    """
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as connection:
        migration_context = MigrationContext.configure(connection)
        heads = migration_context.get_current_heads()
    return heads[0] if heads else None


def get_head_revision() -> str | None:
    """Return the latest revision ID available in AIMBAT's migration scripts.

    Reads `_migrations/versions/` on disk only — needs no database
    connection, so it is safe to call from contexts where opening one would
    be unsafe (e.g. from inside a SQLAlchemy `connect` event, before the
    connection being established has been returned to the pool).

    Returns:
        The head revision ID. `None` only if there are no migrations at all.
    """
    from alembic.script import ScriptDirectory

    script_dir = ScriptDirectory(str(_migrations_dir()))
    return script_dir.get_current_head()


def stamp_head(engine: Engine) -> None:
    """Mark `engine`'s database as being at the latest Alembic revision.

    Writes Alembic's bookkeeping only — runs no migration DDL. Intended for
    a database whose schema is already known to match `head`, e.g.
    immediately after `create_project()` creates a brand new one via
    `SQLModel.metadata.create_all()` rather than via a migration.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.
    """
    from alembic import command

    command.stamp(_alembic_config(engine), "head")


def upgrade_project(engine: Engine) -> None:
    """Upgrade the project database to the latest Alembic revision.

    Handles the normal case (an already-stamped database with pending
    migrations), the legacy case (a pre-Alembic database with no
    `alembic_version` table), and an unrecognised-revision case
    automatically:

    - If the database is already stamped at a revision this installation's
      migration scripts recognise as an ancestor of `head` (including
      `head` itself), this simply runs any pending migrations.
    - If it's stamped at a revision this installation *doesn't* recognise
      at all (e.g. created by a different/newer AIMBAT release, or a
      corrupted `alembic_version` value), this raises `SchemaMismatchError`
      immediately rather than calling into Alembic, which would otherwise
      fail with a raw, unhelpful "Can't locate revision identified by ..."
      error.
    - If it has never been stamped but already has *some* schema (a
      pre-Alembic database), that schema is checked against every known
      revision, not just `head` (see `_find_matching_revision`) - a
      database that skipped an AIMBAT release and matches an older
      revision is stamped at *that* revision and then upgraded the rest of
      the way, not rejected just because it isn't already at head. If it
      doesn't match any known revision at all, this raises
      `SchemaMismatchError` rather than guessing — silently stamping a
      database whose schema doesn't actually match would tell Alembic's
      bookkeeping "this is up to date" while it is actually missing
      columns/tables, turning a loud, safe failure into a silent one.
    - If it has never been stamped *and* has no schema at all (a genuinely
      empty/new database), it is built from scratch by running the full
      migration chain — no comparison or stamping shortcut needed, since
      there is nothing pre-existing that could conflict.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.

    Raises:
        SchemaMismatchError: If the database has no Alembic version history
            and its live schema doesn't match any known AIMBAT schema
            version, or if it's stamped at a revision this installation's
            migration scripts don't recognise at all.
    """
    from alembic import command
    from sqlalchemy import inspect

    config = _alembic_config(engine)
    current_revision = get_current_revision(engine)

    if (
        current_revision is not None
        and current_revision not in _known_ancestors_of_head()
    ):
        raise SchemaMismatchError(
            f"The database at {engine.url} is stamped at schema version "
            f"'{current_revision}', which this AIMBAT installation doesn't "
            "recognise - it may have been created by a different or newer "
            "AIMBAT release, or the version record may be corrupted. This "
            "can't be resolved automatically. Manual intervention is required."
        )

    if current_revision is None:
        with engine.connect() as connection:
            has_existing_schema = bool(inspect(connection).get_table_names())

        if has_existing_schema:
            matched_revision = _find_matching_revision(engine)

            if matched_revision is None:
                raise SchemaMismatchError(
                    f"The database at {engine.url} has no Alembic version "
                    "history, and its schema doesn't match any known AIMBAT "
                    "schema version, so it can't be upgraded automatically. "
                    "This usually means the project was created by a very "
                    "old version of AIMBAT. Manual intervention is required."
                )

            logger.info(
                f"No Alembic history found for {engine.url}, but its schema "
                f"matches revision {matched_revision!r} exactly - stamping "
                "at that revision before upgrading the rest of the way."
            )
            command.stamp(config, matched_revision)
        # else: genuinely empty database - fall through to `command.upgrade`
        # below, which builds the schema from scratch via the full
        # migration chain, exactly like a brand new install.

    command.upgrade(config, "head")
