from sqlalchemy.exc import NoResultFound
from aimbat.logger import logger
from aimbat.lib.db import engine
from aimbat.lib.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatStation,
)
from sqlmodel import SQLModel, Session, select, text
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import aimbat.lib.event as event
import aimbat.lib.seismogram as seismogram
import aimbat.lib.station as station


def _project_exists() -> bool:
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


def create_project() -> None:
    """Create a new AIMBAT project."""

    # import this to create tables below
    import aimbat.lib.models  # noqa: F401

    logger.info(f"Creating new project in {engine=}.")

    if _project_exists():
        raise RuntimeError(
            f"Unable to create a new project: project already exists in {engine=}!"
        )

    logger.debug("Creating database tables and loading defaults.")

    SQLModel.metadata.create_all(engine)
    if engine.driver == "pysqlite":
        with engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))  # for SQLite only

    # This trigger ensures that only one event can be active at a time
    with engine.connect() as connection:
        connection.execute(
            text(
                """CREATE TRIGGER single_active_event
        BEFORE UPDATE ON aimbatevent
        FOR EACH ROW
        WHEN NEW.active = TRUE
        BEGIN
            UPDATE aimbatevent SET active = NULL
        WHERE active = TRUE AND id != NEW.id;
        END;
    """
            )
        )


def delete_project() -> None:
    """Delete the AIMBAT project.

    Raises:
        RuntimeError: If unable to delete project.
    """

    logger.info(f"Deleting project in {engine=}.")

    if _project_exists():
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


def print_project_info() -> None:
    """Show AIMBAT project information.

    Parameters:
        engine: Database engine.

    Raises:
        RuntimeError: If no project found.
    """

    logger.info("Printing project info.")

    if not _project_exists():
        raise RuntimeError(
            'No AIMBAT project found. Try running "aimbat project create" first.'
        )

    with Session(engine) as session:
        grid = Table.grid(expand=False)
        grid.add_column()
        grid.add_column(justify="left")
        if engine.driver == "pysqlite":
            project = str(engine.url.database)
            grid.add_row("AIMBAT Project File: ", project)

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
            active_event = event.get_active_event(session)
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
