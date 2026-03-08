"""
Manage AIMBAT projects.

This command manages projects. By default, the project consists
of a file called `aimbat.db` in the current working directory. All aimbat
commands must be executed from the same directory. The location (and name) of
the project file may also be specified by setting the `AIMBAT_PROJECT`
environment variable to the desired filename. Alternatively, `aimbat` can be
executed with a database url directly.
"""

from cyclopts import App

from .common import DebugParameter, GlobalParameters, simple_exception

app = App(name="project", help=__doc__, help_format="markdown")


@app.command(name="create")
@simple_exception
def cli_project_create(*, _: DebugParameter = DebugParameter()) -> None:
    """Create a new AIMBAT project in the current directory.

    Initialises a new project database (`aimbat.db` by default). Run this
    once before adding data with `aimbat data add`.
    """
    from aimbat.core import create_project
    from aimbat.db import engine

    create_project(engine)


@app.command(name="delete")
@simple_exception
def cli_project_delete(*, _: DebugParameter = DebugParameter()) -> None:
    """Delete project (note: this does *not* delete seismogram files)."""
    from aimbat.core import delete_project
    from aimbat.db import engine

    delete_project(engine)


@app.command(name="info")
@simple_exception
def cli_project_info(
    *, global_parameters: GlobalParameters = GlobalParameters()
) -> None:
    """Show information on an existing project."""

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from sqlalchemy.exc import NoResultFound
    from sqlmodel import Session, select

    import aimbat.core._event as event
    import aimbat.core._seismogram as seismogram
    import aimbat.core._station as station
    from aimbat.core import resolve_event
    from aimbat.core._project import _project_exists
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatStation

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
            target_event = resolve_event(session, global_parameters.event_id)
            target_event_id = target_event.id
            active_stations = len(station.get_stations_in_event(session, target_event))
            seismograms_in_event = len(target_event.seismograms)
            selected_seismograms_in_event = len(
                seismogram.get_selected_seismograms(session, event=target_event)
            )
        except (NoResultFound, ValueError, RuntimeError):
            target_event_id = None
            active_stations = None
            seismograms_in_event = None
            selected_seismograms_in_event = None

        event_label = (
            "Selected Event ID: "
            if global_parameters.event_id
            else "Default Event ID: "
        )
        grid.add_row(event_label, f"{target_event_id}")
        grid.add_row(
            "Number of Stations in Project (total/selected event): ",
            f"({stations}/{active_stations})",
        )

        grid.add_row(
            "Number of Seismograms in Project (total/selected): ",
            f"({seismograms}/{selected_seismograms})",
        )
        grid.add_row(
            "Number of Seismograms in Selected Event (total/selected): ",
            f"({seismograms_in_event}/{selected_seismograms_in_event})",
        )

        console = Console()
        console.print(
            Panel(grid, title="Project Info", title_align="left", border_style="dim")
        )


if __name__ == "__main__":
    app()
