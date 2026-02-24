from aimbat.core import get_active_event
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatStation,
)
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import SQLModel, Session, select, text
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import aimbat.core._event as event
import aimbat.core._seismogram as seismogram
import aimbat.core._station as station

__all__ = ["create_project", "delete_project", "print_project_info"]


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


def print_project_info(engine: Engine) -> None:
    """Show AIMBAT project information.

    Raises:
        RuntimeError: If no project found.
    """

    logger.info("Printing project info.")

    if not _project_exists(engine):
        raise RuntimeError(
            'No AIMBAT project found. Try running "aimbat project create" first.'
        )

    with Session(engine) as session:
        grid = Table.grid(expand=False)
        grid.add_column()
        grid.add_column(justify="left")
        if engine.driver == "pysqlite":
            if engine.url.database == ":memory:":
                grid.add_row("AIMBAT Project: ", "in-memory database")
            else:
                grid.add_row("AIMBAT Project File: ", str(engine.url.database))

        events = len(session.exec(select(AimbatEvent)).all())
        completed_events = len(event.get_completed_events(session))
        stations = len(session.exec(select(AimbatStation)).all())
        seismograms = len(session.exec(select(AimbatSeismogram)).all())
        selected_seismograms = len(
            seismogram.get_selected_seismograms(session, all_events=True)
        )

        grid.add_row(
            "Number of Events (total/completed): ",
            f"({events}/{completed_events})",
        )

        try:
            active_event = get_active_event(session)
            active_event_id = active_event.id
            active_stations = len(station.get_stations_in_event(session, active_event))
            seismograms_in_event = len(active_event.seismograms)
            selected_seismograms_in_event = len(
                seismogram.get_selected_seismograms(session)
            )
        except NoResultFound:
            active_event_id = None
            active_stations = None
            seismograms_in_event = None
            selected_seismograms_in_event = None
        grid.add_row("Active Event ID: ", f"{active_event_id}")
        grid.add_row(
            "Number of Stations in Project (total/active event): ",
            f"({stations}/{active_stations})",
        )

        grid.add_row(
            "Number of Seismograms in Project (total/selected): ",
            f"({seismograms}/{selected_seismograms})",
        )
        grid.add_row(
            "Number of Seismograms in Active Event (total/selected): ",
            f"({seismograms_in_event}/{selected_seismograms_in_event})",
        )

        console = Console()
        console.print(
            Panel(grid, title="Project Info", title_align="left", border_style="dim")
        )
