"""Create and delete AIMBAT project databases."""

from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import SQLModel, text

from aimbat.logger import logger

__all__ = ["create_project", "delete_project"]


def _project_exists(engine: Engine) -> bool:
    """Check whether an AIMBAT project already exists at `engine`.

    Presence is inferred from the `aimbatevent` table rather than any
    explicit marker.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.

    Returns:
        True if the `aimbatevent` table exists, False otherwise.

    Raises:
        RuntimeError: If `engine`'s driver is not `pysqlite`.
    """

    _TABLE_TO_CHECK = "aimbatevent"

    logger.debug(
        f"Checking if project already exists with {engine=} by searching for the {_TABLE_TO_CHECK} table."
    )

    if engine.driver == "pysqlite":
        with engine.connect() as connection:
            result = connection.execute(
                text(f"PRAGMA table_info({_TABLE_TO_CHECK})")
            ).all()
            if result == []:
                logger.debug("No project found.")
                return False
            logger.debug("Project found.")
            return True
    raise RuntimeError(
        f"Unable to determine if project already exists using {engine=}."
    )


def create_project(engine: Engine) -> None:
    """Initialise a new AIMBAT project database schema.

    Creates all tables from `SQLModel.metadata` and stamps the new database
    at the latest Alembic revision.

    Tables and the stamp are written in one transaction, so a
    failure partway through leaves no half-made project behind: SQLite rolls
    schema changes back like any other statement. A database file may still
    be created on disk by the connection itself, but it will hold no AIMBAT
    tables, and `create_project` can simply be run again.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the target database.

    Raises:
        RuntimeError: If a project schema already exists in the target database.
    """

    # Import locally to ensure SQLModel registers all table metadata before create_all()
    import aimbat.models  # noqa: F401

    logger.info(f"Creating new project in {engine.url}.")

    if _project_exists(engine):
        raise RuntimeError(
            f"Unable to create a new project: project already exists at {engine.url}!"
        )

    logger.debug("Creating database tables and loading defaults.")

    # Import locally to break a circular import at module level.
    from aimbat.core._migrations import stamp_head

    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        # SQLite can roll DDL back, but the driver commits before each DDL
        # statement unless the transaction is opened by hand - which would
        # leave a failure partway through this function half-applied, as a
        # database with tables but no stamp. AUTOCOMMIT hands transaction
        # control over, so the BEGIN below covers the tables and the stamp
        # together.
        connection.exec_driver_sql("BEGIN")
        try:
            SQLModel.metadata.create_all(connection)

            # An unstamped database with tables is refused by
            # `upgrade_project`, so stamp in the same transaction.
            stamp_head(connection)
        except Exception:
            connection.exec_driver_sql("ROLLBACK")
            raise

        connection.exec_driver_sql("COMMIT")


def delete_project(engine: Engine) -> None:
    """Delete the AIMBAT project.

    For a file-based SQLite database, deletes the database file itself. For
    an in-memory database, this is a no-op beyond disposing the engine.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the
            target database.

    Raises:
        RuntimeError: If no project exists at `engine`, or if `engine`'s
            driver is not `pysqlite`.
    """

    logger.info(f"Deleting project at {engine.url}.")

    if not _project_exists(engine):
        raise RuntimeError("No project found to delete.")

    if engine.driver == "pysqlite":
        database = engine.url.database
        engine.dispose()
        if database == ":memory:":
            logger.info("Running database in memory, nothing to delete.")
            return
        elif database:
            project_path = Path(database)
            resolved = project_path.resolve()
            if resolved == Path(resolved.anchor) or resolved == Path.home():
                raise RuntimeError(
                    f"Refusing to delete suspicious project path: {resolved}."
                )
            logger.info(f"Deleting project file: {project_path}.")
            project_path.unlink()
            for suffix in ("-wal", "-shm"):
                project_path.with_name(project_path.name + suffix).unlink(
                    missing_ok=True
                )
            return

    raise RuntimeError(
        f"Unable to delete project: unsupported engine driver '{engine.driver}'."
    )
