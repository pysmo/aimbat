from sqlalchemy import Engine
from sqlmodel import SQLModel, text
from pathlib import Path
from aimbat.logger import logger

__all__ = ["create_project", "delete_project"]


def _project_exists(engine: Engine) -> bool:
    """Check if AIMBAT project exists by checking if aimbatevent table exists."""

    _TABLE_TO_CHECK = "aimbatevent"

    logger.info(
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
    """Initializes a new AIMBAT project database schema and triggers.

    Args:
        engine: The SQLAlchemy/SQLModel Engine instance connected to the target database.

    Raises:
        RuntimeError: If a project schema already exists in the target database.
    """

    # Import locally to ensure SQLModel registers all table metadata before create_all()
    import aimbat.models  # noqa: F401

    logger.info(f"Creating new project in {engine.url}")

    if _project_exists(engine):
        raise RuntimeError(
            f"Unable to create a new project: project already exists at {engine.url}!"
        )

    logger.debug("Creating database tables and loading defaults.")

    SQLModel.metadata.create_all(engine)

    if engine.name == "sqlite":
        with engine.begin() as connection:
            # Trigger 1: Handle updates to existing rows
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS single_active_event_update
                BEFORE UPDATE ON aimbatevent
                FOR EACH ROW WHEN NEW.active = TRUE
                BEGIN
                    UPDATE aimbatevent SET active = NULL 
                    WHERE active = TRUE AND id != NEW.id;
                END;
            """))

            # Trigger 2: Handle brand new active events being inserted
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS single_active_event_insert
                BEFORE INSERT ON aimbatevent
                FOR EACH ROW WHEN NEW.active = TRUE
                BEGIN
                    UPDATE aimbatevent SET active = NULL
                    WHERE active = TRUE;
                END;
            """))

            # Trigger 3: Track last modification time when event parameters change
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS event_modified_on_params_update
                AFTER UPDATE ON aimbateventparameters
                BEGIN
                    UPDATE aimbatevent SET last_modified = datetime('now')
                    WHERE id = NEW.event_id;
                END;
            """))

            # Trigger 4: Track last modification time when seismogram parameters change
            connection.execute(text("""
                CREATE TRIGGER IF NOT EXISTS event_modified_on_seis_params_update
                AFTER UPDATE ON aimbatseismogramparameters
                BEGIN
                    UPDATE aimbatevent 
                    SET last_modified = strftime('%Y-%m-%d %H:%M:%f', 'now')
                    WHERE id = (
                        SELECT event_id FROM aimbatseismogram
                        WHERE id = NEW.seismogram_id
                    );
                END;
            """))


def delete_project(engine: Engine) -> None:
    """Delete the AIMBAT project.

    Raises:
        RuntimeError: If unable to delete project.
    """

    logger.info(f"Deleting project in {engine=}.")

    if _project_exists(engine):
        if engine.driver == "pysqlite":
            database = engine.url.database
            engine.dispose()
            if database == ":memory:":
                logger.info("Running database in memory, nothing to delete.")
                return
            elif database:
                project_path = Path(database)
                logger.info(f"Deleting project file: {project_path=}")
                project_path.unlink()
                return
    raise RuntimeError("Unable to find/delete project.")
