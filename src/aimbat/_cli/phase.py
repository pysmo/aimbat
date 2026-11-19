"""View and manage the phases of events.

A phase is one seismic phase of an event (e.g. P or PKP), and the unit of
processing: parameters, quality, snapshots and the processing state of each
seismogram belong to a phase. Phases are created when initial picks are
added. Commands that act on one phase take `--phase NAME`, or the
`DEFAULT_PHASE` environment variable, which may be omitted when the event has
only one phase.
"""

import uuid
from typing import Annotated, Literal

from cyclopts import App, Parameter
from sqlmodel import Session

from aimbat.models import AimbatEvent
from aimbat.types import PhaseParameter

from .common import (
    JsonDumpParameters,
    PhaseDebugParameters,
    TableParameters,
    confirm_or_abort,
    event_parameter_is_all,
    event_parameter_with_all,
    handle_issues,
    id_label,
    phase_filter_parameter,
    print_json_dump,
    print_quality_table,
)

__all__ = [
    "cli_phase_completed",
    "cli_phase_dump",
    "cli_phase_list",
    "cli_phase_parameter_dump",
    "cli_phase_parameter_get",
    "cli_phase_parameter_list",
    "cli_phase_parameter_set",
    "cli_phase_quality_dump",
    "cli_phase_quality_list",
    "cli_phase_remove",
    "cli_phase_rename",
]

app = App(name="phase", help=__doc__, help_format="markdown")
_parameter = App(
    name="parameter", help="Manage phase parameters.", help_format="markdown"
)
_quality = App(
    name="quality", help="View phase quality metrics.", help_format="markdown"
)
app.command(_parameter)
app.command(_quality)


def _event_title(
    session: Session, subject: str, event_id: uuid.UUID | Literal["all"], *, raw: bool
) -> tuple[str, uuid.UUID | None]:
    """Return a table title and the event to filter by, `None` for all events."""
    from aimbat.core import resolve_event

    if event_parameter_is_all(event_id):
        return f"{subject} for all events", None
    event = resolve_event(session, event_id)
    label = id_label(session, AimbatEvent, event.id, raw=raw)
    return f"{subject} for event: {label}", event.id


@app.command(name="list")
@handle_issues
def cli_phase_list(
    event_id: Annotated[uuid.UUID | Literal["all"], event_parameter_with_all()],
    *,
    phase: Annotated[str | None, phase_filter_parameter()] = None,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Print a table of the phases of an event or of all events.

    Shows the number of seismograms and selected seismograms of each phase,
    whether it is marked as completed, and whether it has MCCC results valid
    for its current parameters.
    """
    from aimbat.core import dump_phase_table
    from aimbat.db import engine
    from aimbat.models import AimbatPhaseRead

    from .common import json_to_table

    raw = table_parameters.raw
    exclude = {"short_id", "short_event_id"} if raw else {"id", "event_id"}

    with Session(engine) as session:
        title, filter_id = _event_title(session, "Phases", event_id, raw=raw)
        if filter_id is not None:
            exclude |= {"event_id", "short_event_id", "event_time"}
        json_to_table(
            data=dump_phase_table(
                session,
                from_read_model=True,
                exclude=exclude,
                event_id=filter_id,
                name=phase,
            ),
            model=AimbatPhaseRead,
            title=title,
            raw=raw,
        )


@app.command(name="dump")
@handle_issues
def cli_phase_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump the contents of the AIMBAT phase table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.core import dump_phase_table

    print_json_dump(dump_phase_table, by_alias=dump_parameters.by_alias)


@app.command(name="completed")
@handle_issues
def cli_phase_completed(*, phase_parameters: PhaseDebugParameters) -> None:
    """Toggle whether a phase is marked as completed.

    The flag is bookkeeping only and does not affect processing. An event
    counts as completed when all of its phases are.
    """
    from rich.console import Console

    from aimbat.actions import toggle_phase_completed

    completed = toggle_phase_completed(phase_parameters.phase_id())
    Console().print(
        "Phase marked as completed." if completed else "Phase marked as not completed."
    )


@app.command(name="rename")
@handle_issues
def cli_phase_rename(name: str, *, phase_parameters: PhaseDebugParameters) -> None:
    """Rename a phase.

    Picks of the event named for the phase are renamed with it. The new
    name must not be used by another phase of the event.

    Args:
        name: New name of the phase.
        phase_parameters: Event, phase and debug mode.
    """
    from aimbat.actions import rename_phase

    rename_phase(phase_parameters.phase_id(), name)


@app.command(name="remove")
@handle_issues
def cli_phase_remove(
    *,
    phase_parameters: PhaseDebugParameters,
    yes: Annotated[
        bool,
        Parameter(
            name=["--yes", "-y"], help="Skip the confirmation prompt.", negative=()
        ),
    ] = False,
) -> None:
    """Remove a phase of an event.

    The initial picks, parameters, quality and snapshots of the phase are
    deleted with it. Picks of the event named for the phase are dismissed,
    and `aimbat pick restore` brings them back.
    """
    from rich.console import Console

    from aimbat.actions import RemovePhaseResult, remove_phase
    from aimbat.utils.formatters import fmt_timestamp

    def confirm(result: RemovePhaseResult) -> bool:
        confirm_or_abort(
            f"Remove phase {result.phase_name} of event "
            + f"{fmt_timestamp(result.event_time)}, with {result.rows} initial "
            + f"pick(s) and {result.snapshots} snapshot(s), and dismiss "
            + f"{result.dismissed_picks} pick(s)?",
            yes=yes,
        )
        return True

    result = remove_phase(phase_parameters.phase_id(), confirm=confirm)
    Console().print(
        f"Removed phase {result.phase_name} of event "
        + f"{fmt_timestamp(result.event_time)}: {result.rows} initial pick(s) and "
        + f"{result.snapshots} snapshot(s) deleted, {result.dismissed_picks} "
        + "pick(s) dismissed."
    )


@_parameter.command(name="get")
@handle_issues
def cli_phase_parameter_get(
    name: PhaseParameter, *, phase_parameters: PhaseDebugParameters
) -> None:
    """Get the value of a phase parameter.

    Args:
        name: Phase parameter name.
        phase_parameters: Event, phase and debug mode.
    """
    from aimbat.core import resolve_phase
    from aimbat.db import engine

    with Session(engine) as session:
        parameters = resolve_phase(
            session, phase_parameters.event_id, phase_parameters.phase
        ).parameters
        print(parameters.model_dump(mode="json").get(name))


@_parameter.command(name="set")
@handle_issues
def cli_phase_parameter_set(
    name: PhaseParameter, value: str, *, phase_parameters: PhaseDebugParameters
) -> None:
    """Set the value of a phase parameter.

    Args:
        name: Phase parameter name.
        value: New parameter value.
        phase_parameters: Event, phase and debug mode.
    """
    from aimbat.actions import set_phase_parameters

    set_phase_parameters(phase_parameters.phase_id(), {name: value}, validate_iccs=True)


@_parameter.command(name="dump")
@handle_issues
def cli_phase_parameter_dump(
    *,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Dump the phase parameter table to JSON."""
    from aimbat.core import dump_phase_parameter_table

    print_json_dump(dump_phase_parameter_table, by_alias=dump_parameters.by_alias)


@_parameter.command(name="list")
@handle_issues
def cli_phase_parameter_list(
    event_id: Annotated[uuid.UUID | Literal["all"], event_parameter_with_all()],
    *,
    phase: Annotated[str | None, phase_filter_parameter()] = None,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """List the processing parameters of the phases of an event or of all events.

    Displays all phase parameters (e.g. time window, bandpass filter
    settings, minimum cc) in a table, one row per phase.
    """
    from aimbat.core import dump_phase_parameter_table
    from aimbat.db import engine
    from aimbat.models import AimbatPhaseParameters
    from aimbat.models._format import RichColSpec
    from aimbat.utils import uuid_shortener

    from .common import json_to_table

    raw = table_parameters.raw

    with Session(engine) as session:
        title, filter_id = _event_title(session, "Phase parameters", event_id, raw=raw)
        data = dump_phase_parameter_table(session, event_id=filter_id, name=phase)
        phase_names = {row["phase_id"]: row["phase_name"] for row in data}

        json_to_table(
            model=AimbatPhaseParameters,
            title=title,
            data=data,
            raw=raw,
            col_specs={
                "id": RichColSpec(
                    formatter=lambda x: uuid_shortener(
                        session, AimbatPhaseParameters, str_uuid=x
                    )
                ),
                "phase_id": RichColSpec(
                    display_title="Phase", formatter=lambda x: phase_names[x]
                ),
            },
            column_order=["id", "phase_id"],
        )


@_quality.command(name="dump")
@handle_issues
def cli_phase_quality_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump phase quality statistics to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.core import dump_phase_quality_table

    print_json_dump(dump_phase_quality_table, by_alias=dump_parameters.by_alias)


@_quality.command(name="list")
@handle_issues
def cli_phase_quality_list(
    event_id: Annotated[uuid.UUID | Literal["all"], event_parameter_with_all()],
    *,
    phase: Annotated[str | None, phase_filter_parameter()] = None,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Show aggregated quality statistics for the phases of an event or of all events.

    Displays ICCS and MCCC quality metrics (means, SEMs, RMSE) aggregated
    across the seismograms of each phase.
    """
    from aimbat.core import dump_phase_quality_table
    from aimbat.db import engine

    raw = table_parameters.raw

    with Session(engine) as session:
        title, filter_id = _event_title(
            session, "Quality statistics", event_id, raw=raw
        )
        print_quality_table(
            session,
            dump_phase_quality_table,
            title=title,
            filter_id=filter_id,
            id_field="event_id",
            id_columns={"event_id": AimbatEvent},
            raw=raw,
            filters={"name": phase},
        )


if __name__ == "__main__":
    app()
