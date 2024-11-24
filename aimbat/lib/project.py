from aimbat.lib.common import ic
from aimbat.lib.db import engine
from aimbat.lib.defaults import load_global_defaults
from aimbat.lib.event import get_completed_events, get_active_event
from aimbat.lib.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramParameter,
    AimbatStation,
)
from sqlalchemy import Engine
from sqlmodel import SQLModel, Session, select, text
from pathlib import Path
from typing import Any
from rich.console import Console


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
        select_selected_seismograms_in_project = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameter)
            .where(AimbatSeismogramParameter.select == 1)
        )

        events_in_project = session.exec(select(AimbatEvent)).all()
        completed_events_in_project = get_completed_events(session)
        all_stations_in_project = session.exec(select(AimbatStation)).all()
        all_seismograms_in_project = session.exec(select(AimbatSeismogram)).all()
        number_of_stations_in_active_event = None
        try:
            selected_event = get_active_event(session)
            number_of_stations_in_active_event = len(selected_event.stations)
        except RuntimeError:
            selected_event = None

        seismograms_selected = session.exec(
            select_selected_seismograms_in_project
        ).all()

        console = Console()
        if engine.driver == "pysqlite":
            project = _project_file(engine)
            console.print("AIMBAT Project File: ", project)
        console.print(
            "Number of Events (total/completed):",
            f"({len(events_in_project)}/{len(completed_events_in_project)})",
        )
        console.print("Active Event ID:", getattr(selected_event, "id", None))
        console.print(
            f"Number of Stations (total/active event): ({len(all_stations_in_project)}/{number_of_stations_in_active_event})",
        )
        console.print(
            "Number of Seismograms (total/selected): ",
            f"({len(all_seismograms_in_project)}/{len(seismograms_selected)})",
        )
