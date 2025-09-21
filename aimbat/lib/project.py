from aimbat.lib.common import logger
from aimbat.lib.db import engine
from aimbat.lib.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatStation,
)
from sqlalchemy import Engine
from sqlmodel import SQLModel, Session, select, text
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import aimbat.lib.event as event
import aimbat.lib.seismogram as seismogram
import aimbat.lib.station as station


def _project_exists(engine: Engine) -> bool:
    """Check if AIMBAT project exists by checking if aimbatdefaults table exists."""

    logger.info("Checking if project already exists.")

    if engine.driver == "pysqlite":
        with engine.connect() as connection:
            result = connection.execute(text("PRAGMA table_info(aimbatdefaults)")).all()
            if result == []:
                return False
            return True
    raise RuntimeError(
        f"Unable to determine if project already exists using {engine=}."
    )


def _project_file_from_engine(engine: Engine) -> Path:
    """Get filename from sqlite engine

    Parameters:
        engine: Database engine.

    Raises:
        RuntimeError: If unable to determine project file.
    """

    logger.info(f"Determining project file from {engine=}.")

    with engine.connect() as connection:
        dbs = connection.execute(text("PRAGMA database_list")).all()
        assert dbs is not None
        for db in dbs:
            if db[1] == "main":
                db_file = db[-1]
                return Path(db_file)
    raise RuntimeError(f"Unable to to determine project file using {engine=}.")


def create_project(engine: Engine = engine) -> None:
    """Create a new AIMBAT project.

    Parameters:
        engine: Database engine.
    """
    #
    # import this to create tables below
    import aimbat.lib.models  # noqa: F401

    logger.info(f"Creating new project in {engine=}.")

    if _project_exists(engine):
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


def delete_project(engine: Engine = engine) -> None:
    """Delete the AIMBAT project.

    Parameters:
        engine: Database engine.

    Raises:
        RuntimeError: If unable to delete project.
    """

    logger.info(f"Deleting project in {engine=}.")

    if _project_exists(engine):
        if engine.driver == "pysqlite":
            project = _project_file_from_engine(engine)
            engine.dispose()
            try:
                logger.info(f"Deleting project file: {project=}")
                project.unlink()
                return
            except IsADirectoryError:
                logger.info("No file found - possibly running in-memory database?")
                return
    raise RuntimeError("Unable to find/delete project.")


def print_project_info(engine: Engine = engine) -> None:
    """Show AIMBAT project information.

    Parameters:
        engine: Database engine.

    Raises:
        RuntimeError: If no project found.
    """

    logger.info(f"Printing project info in {engine=}.")

    if not _project_exists(engine):
        raise RuntimeError("No AIMBAT project found.")

    with Session(engine) as session:
        grid = Table.grid(expand=False)
        grid.add_column()
        grid.add_column(justify="left")
        if engine.driver == "pysqlite":
            project = str(_project_file_from_engine(engine))
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
        except RuntimeError:
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
