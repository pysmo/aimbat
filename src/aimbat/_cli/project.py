"""Manage AIMBAT projects.

This command manages projects. By default, the project consists
of a file called `aimbat.db` in the current working directory. All aimbat
commands must be executed from the same directory. The location (and name) of
the project file may also be specified by setting the `AIMBAT_PROJECT`
environment variable to the desired filename. Alternatively, `aimbat` can be
executed with a database url directly.
"""

from typing import Annotated
from uuid import UUID

from cyclopts import App

from .common import (
    ConfirmParameters,
    DebugParameter,
    confirm_or_abort,
    event_parameter,
    handle_issues,
    phase_parameter,
)

app = App(name="project", help=__doc__, help_format="markdown")


@app.command(name="create")
@handle_issues
def cli_project_create(*, _: DebugParameter = DebugParameter()) -> None:
    """Create a new AIMBAT project in the current directory.

    Initialises a new project database (`aimbat.db` by default). Run this
    once before adding data with `aimbat data add`.
    """
    from aimbat.core import create_project
    from aimbat.db import engine

    create_project(engine)


@app.command(name="delete")
@handle_issues
def cli_project_delete(*, confirm: ConfirmParameters = ConfirmParameters()) -> None:
    """Delete the AIMBAT project database.

    Does not delete the underlying seismogram data source files.
    """
    from aimbat.core import delete_project
    from aimbat.db import engine

    confirm_or_abort("Delete the AIMBAT project database?", yes=confirm.yes)
    delete_project(engine)


@app.command(name="info")
@handle_issues
def cli_project_info(
    event_id: Annotated[UUID | None, event_parameter()] = None,
    *,
    phase: Annotated[str | None, phase_parameter()] = None,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Show information on an existing project."""

    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from sqlalchemy.exc import NoResultFound
    from sqlmodel import Session, func, select

    from aimbat.core import (
        AmbiguousPhaseError,
        get_completed_events,
        get_completed_phases,
        get_selected_rows,
        get_stations_in_event,
        resolve_event,
        resolve_phase,
    )
    from aimbat.core._project import _project_exists
    from aimbat.db import engine
    from aimbat.models import AimbatEvent, AimbatPhase, AimbatSeismogram, AimbatStation

    if not _project_exists(engine):
        raise RuntimeError(
            'No AIMBAT project found. Try running "aimbat project create" first.'
        )

    def _count(
        model: type[AimbatEvent | AimbatPhase | AimbatSeismogram | AimbatStation],
    ) -> int:
        return session.exec(select(func.count()).select_from(model)).one()

    with Session(engine) as session:
        grid = Table.grid(expand=False)
        grid.add_column()
        grid.add_column(justify="left")
        if engine.driver == "pysqlite":
            if engine.url.database == ":memory:":
                grid.add_row("AIMBAT Project: ", "in-memory database")
            else:
                grid.add_row("AIMBAT Project File: ", str(engine.url.database))

        events = _count(AimbatEvent)
        completed_events = len(get_completed_events(session))
        phases = _count(AimbatPhase)
        completed_phases = len(get_completed_phases(session))
        stations = _count(AimbatStation)
        seismograms = _count(AimbatSeismogram)

        target_event_id = None
        active_stations = None
        seismograms_in_event = None
        phase_name = None
        seismograms_in_phase = None
        selected_in_phase = None
        try:
            target_event = resolve_event(session, event_id)
            target_event_id = target_event.id
            active_stations = len(get_stations_in_event(session, target_event.id))
            seismograms_in_event = len(target_event.seismograms)
            target_phase = resolve_phase(session, target_event.id, phase)
            phase_name = target_phase.name
            seismograms_in_phase = len(target_phase.seismogram_parameters)
            selected_in_phase = len(get_selected_rows(session, target_phase.id))
        except (NoResultFound, AmbiguousPhaseError, ValueError, RuntimeError):
            pass

        def _fmt(value: int | str | UUID | None) -> str:
            return "—" if value is None else str(value)

        grid.add_row(
            "Number of Events (total/completed): ",
            f"({events}/{completed_events})",
        )
        grid.add_row(
            "Number of Phases (total/completed): ",
            f"({phases}/{completed_phases})",
        )
        grid.add_row("Selected Event ID: ", _fmt(target_event_id))
        grid.add_row("Selected Phase: ", _fmt(phase_name))
        grid.add_row(
            "Number of Stations in Project (total/selected event): ",
            f"({stations}/{_fmt(active_stations)})",
        )
        grid.add_row(
            "Number of Seismograms in Project (total/selected event): ",
            f"({seismograms}/{_fmt(seismograms_in_event)})",
        )
        grid.add_row(
            "Number of Seismograms in Selected Phase (total/selected): ",
            f"({_fmt(seismograms_in_phase)}/{_fmt(selected_in_phase)})",
        )

        console = Console()
        console.print(
            Panel(grid, title="Project Info", title_align="left", border_style="dim")
        )


if __name__ == "__main__":
    app()
