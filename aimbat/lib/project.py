from aimbat.lib.common import ic
from aimbat.lib.db import engine
from aimbat.lib.defaults import load_global_defaults
from aimbat.lib.event import get_completed_events, get_active_event
from aimbat.lib.seismogram import get_selected_seismograms
from aimbat.lib.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatStation,
)
from sqlalchemy import Engine
from sqlmodel import SQLModel, Session, select, text
from pathlib import Path
from typing import Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


def _project_exists(engine: Engine) -> bool:
    """Check if AIMBAT project exists."""

    ic()
    ic(engine)

    if engine.driver == "pysqlite":
        with engine.connect() as connection:
            result = connection.execute(text("PRAGMA table_info(aimbatdefault)")).all()
            if result == []:
                return False
            return True
    raise RuntimeError(
        f"Unable to determine if project already exists using {engine=}."
    )


def _project_file(engine: Engine) -> Path:
    """Get filename from sqlite engine"""
    with engine.connect() as connection:
        dbs = connection.execute(text("PRAGMA database_list")).all()
        assert dbs is not None
        for db in dbs:
            if db[1] == "main":
                db_file = db[-1]
                return Path(db_file)
    raise RuntimeError(f"Unable to to determine project file using {engine=}.")


def create_project(engine: Engine = engine) -> None:
    """Create a new AIMBAT project."""
    import aimbat.lib.models  # noqa: F401

    ic()
    ic(engine)

    if _project_exists(engine):
        raise RuntimeError(
            f"Unable to create a new project: project already exists in {engine=}!"
        )

    # create tables and load defaults
    SQLModel.metadata.create_all(engine)
    if engine.driver == "pysqlite":
        with engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))  # for SQLite only
    with Session(engine) as session:
        load_global_defaults(session)


def delete_project(engine: Engine = engine) -> None:
    """Delete the AIMBAT project."""

    ic()
    ic(engine)

    if _project_exists(engine):
        if engine.driver == "pysqlite":
            project = _project_file(engine)
            try:
                Path(project).unlink()
                ic(f"Deleting {project=}")
            except IsADirectoryError:
                ic("Possibly running in-memory database?")
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Unable to delete project file: {project=} not found."
                )
            finally:
                engine.dispose()
            return
    raise RuntimeError("Unable to delete project.")


def print_project_info(engine: Engine = engine) -> Any:
    """Show AIMBAT project information."""

    ic()
    ic(engine)

    if not _project_exists(engine):
        raise RuntimeError("No AIMBAT project found.")

    with Session(engine) as session:
        grid = Table.grid(expand=False)
        grid.add_column()
        grid.add_column(justify="left")
        if engine.driver == "pysqlite":
            project = str(_project_file(engine))
            grid.add_row("AIMBAT Project File: ", project)

        events = len(session.exec(select(AimbatEvent)).all())
        completed_events = len(get_completed_events(session))
        stations = len(session.exec(select(AimbatStation)).all())
        seismograms = len(session.exec(select(AimbatSeismogram)).all())
        selected_seismograms = len(get_selected_seismograms(session, all_events=True))

        grid.add_row(
            "Number of Events (total/completed): ",
            f"({events}/{completed_events})",
        )

        active_event_id = None
        active_stations = None
        seismograms_in_event = None
        selected_seismograms_in_event = None
        try:
            active_event = get_active_event(session)
            active_event_id = active_event.id
            active_stations = len(active_event.stations)
            seismograms_in_event = len(active_event.seismograms)
            selected_seismograms_in_event = len(get_selected_seismograms(session))
        except RuntimeError:
            pass
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
