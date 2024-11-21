from aimbat.lib.common import ic
from aimbat.lib.db import engine, AIMBAT_PROJECT
from aimbat.lib.models import (
    AimbatEvent,
    AimbatEventParameter,
    AimbatSeismogram,
    AimbatSeismogramParameter,
    AimbatStation,
)
from aimbat.lib.defaults import defaults_load_global_values
from sqlmodel import SQLModel, Session, select, text
from pathlib import Path
from typing import Any
from rich.console import Console
import aimbat.lib.models  # noqa: F401


def project_exists() -> bool:
    """Check if AIMBAT project exists."""

    ic()
    ic(AIMBAT_PROJECT)

    return Path(AIMBAT_PROJECT).exists()


def project_new() -> None:
    """Create a new AIMBAT project."""

    ic()
    ic(AIMBAT_PROJECT)

    # stop here if there is an existing aimbat.db file
    if project_exists():
        raise FileExistsError(
            f"Unable to create a new project: found existing {AIMBAT_PROJECT=}!"
        )

    # create tables and load defaults
    SQLModel.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))  # for SQLite only
    defaults_load_global_values()


def project_del() -> None:
    """Delete the AIMBAT project."""

    ic()
    ic(AIMBAT_PROJECT)

    try:
        Path(AIMBAT_PROJECT).unlink()

    except FileNotFoundError:
        raise FileNotFoundError(
            f"Unable to delete project: {AIMBAT_PROJECT=} not found."
        )
    finally:
        engine.dispose()


def project_print_info() -> Any:
    """Show AIMBAT project information."""

    ic()
    ic(AIMBAT_PROJECT)

    if not Path(AIMBAT_PROJECT).exists():
        raise FileNotFoundError(f"Unable to show info: {AIMBAT_PROJECT=} not found!")

    with Session(engine) as session:
        select_completed_events = (
            select(AimbatEvent)
            .join(AimbatEventParameter)
            .where(AimbatEventParameter.completed == 1)
        )
        select_selected_seismograms = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameter)
            .where(AimbatSeismogramParameter.select == 1)
        )

        all_stations = session.exec(select(AimbatStation)).all()
        all_events = session.exec(select(AimbatEvent)).all()
        completed_events = session.exec(select_completed_events).all()
        all_seismograms = session.exec(select(AimbatSeismogram)).all()
        selected_seismograms = session.exec(select_selected_seismograms).all()
        console = Console()
        console.print("AIMBAT Project File: ", AIMBAT_PROJECT)
        console.print("Number of Stations:", len(all_stations))
        console.print(
            "Number of Events (total/completed): ",
            f"({len(all_events)}/{len(completed_events)})",
        )
        console.print(
            "Number of Seismograms (total/selected): ",
            f"({len(all_seismograms)}/{len(selected_seismograms)})",
        )
