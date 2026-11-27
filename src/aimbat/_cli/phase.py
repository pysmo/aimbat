"""View and manage the phases of events.

A phase is one seismic phase of an event (e.g. P or PKP), and the unit of
processing: parameters, quality, snapshots and the processing state of each
seismogram belong to a phase. Phases are created when initial picks are
added, one for each phase name and component. Commands that act on one
phase take `--phase NAME` and `--component COMPONENT`, or the `DEFAULT_PHASE`
and `DEFAULT_COMPONENT` environment variables. Either may be omitted when the
other selects one phase of the event, and both when the event has only one
phase.
"""

import uuid
from typing import Annotated, Literal

from cyclopts import App, Parameter
from sqlmodel import Session

from aimbat.models import AimbatEvent
from aimbat.types import PhaseParameter

from .common import (
    DebugParameter,
    JsonDumpParameters,
    PhaseDebugParameters,
    TableParameters,
    component_parameter,
    confirm_or_abort,
    default_component,
    event_parameter_is_all,
    event_parameter_with_all,
    handle_issues,
    id_label,
    phase_filter_parameter,
    phase_parameter,
    print_json_dump,
    print_quality_table,
    resolve_phase_option,
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
    """Rename a phase on every component.

    Picks carry a phase name but no component, so the phase is renamed on
    every component of the event, and the picks of the event named for it
    with it. The event must not have a phase of the new name on any of
    those components.

    Args:
        name: New name of the phase.
        phase_parameters: Event, phase and debug mode.
    """
    from rich.console import Console

    from aimbat.actions import rename_phase
    from aimbat.core import get_phases, resolve_phase
    from aimbat.db import engine
    from aimbat.models import phase_label
    from aimbat.utils.formatters import fmt_timestamp

    # Any phase of the name stands for all of them, so no component is needed.
    event_id, old = phase_parameters.event_id, phase_parameters.phase
    with Session(engine) as session:
        phases = get_phases(session, event_id, old)
        if len({p.name for p in phases}) == 1:
            phase_id = phases[0].id
        else:
            phase_id = resolve_phase(session, event_id, old).id
    report = rename_phase(phase_id, name)
    renamed = ", ".join(
        f"{phase_label(report.old_name, c)} to {phase_label(report.new_name, c)}"
        for c in report.components
    )
    Console().print(
        f"Renamed {renamed} of event {fmt_timestamp(report.event_time)}, "
        + f"with {report.picks} pick(s)."
    )


@app.command(name="remove")
@handle_issues
def cli_phase_remove(
    *,
    event_id: Annotated[uuid.UUID | Literal["all"], event_parameter_with_all()],
    phase: Annotated[str | None, phase_parameter()] = None,
    component: Annotated[str | None, component_parameter()] = None,
    dry_run: Annotated[
        bool,
        Parameter(name="dry-run", help="Show what would be removed without saving it."),
    ] = False,
    yes: Annotated[
        bool,
        Parameter(
            name=["--yes", "-y"], help="Skip the confirmation prompt.", negative=()
        ),
    ] = False,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Remove a phase of an event on one component.

    The initial picks, parameters, quality and snapshots of the phase are
    deleted with it. Picks of the event named for the phase on seismograms
    of its component are dismissed, and `aimbat pick restore` brings them
    back. Unmatched picks of the name are dismissed only when the event has
    no phase of the name on another component.

    With `--event all`, the phase of that name and component is removed
    from every event that has it, and both `--phase` and `--component` are
    needed. Events without it are skipped.

    Args:
        event_id: Event of the phase, or "all" for every event.
        phase: Name of the phase.
        component: Component of the phase.
        dry_run: Show what would be removed without saving it.
        yes: Skip the confirmation prompt.
    """
    from rich.console import Console
    from sqlmodel import col, select

    from aimbat.actions import RemovePhaseResult, remove_phases
    from aimbat.db import engine
    from aimbat.models import AimbatPhase, phase_label
    from aimbat.utils.formatters import fmt_timestamp

    if event_parameter_is_all(event_id):
        component = default_component(phase, component)
        if phase is None or component is None:
            raise ValueError(
                "`--phase` and `--component` are needed with `--event all`."
            )
        with Session(engine) as session:
            phase_ids = list(
                session.exec(
                    select(AimbatPhase.id)
                    .join(AimbatEvent)
                    .where(col(AimbatPhase.name) == phase)
                    .where(col(AimbatPhase.component) == component)
                    .order_by(col(AimbatEvent.time))
                ).all()
            )
        if not phase_ids:
            raise ValueError(f"No event has a phase {phase_label(phase, component)}.")
    else:
        phase_ids = [resolve_phase_option(event_id, phase, component)]

    def picks(result: RemovePhaseResult) -> str:
        text = f"{result.dismissed_picks} pick(s)"
        if result.dismissed_unmatched:
            text += f" and {result.dismissed_unmatched} unmatched pick(s)"
        return text

    def kept(result: RemovePhaseResult) -> str:
        if not result.kept_unmatched:
            return ""
        others = ", ".join(
            phase_label(result.phase_name, c) for c in result.other_components
        )
        return f" {result.kept_unmatched} unmatched pick(s) are kept for {others}."

    def kept_in_all(results: list[RemovePhaseResult]) -> str:
        count = sum(r.kept_unmatched for r in results)
        if not count:
            return ""
        name = results[0].phase_name
        others = ", ".join(
            phase_label(name, c)
            for c in sorted(
                {c for r in results if r.kept_unmatched for c in r.other_components}
            )
        )
        return f" {count} unmatched pick(s) are kept for {others}."

    def line(result: RemovePhaseResult) -> str:
        verb = "Removed" if result.removed else "Would remove"
        return (
            f"{verb} phase {phase_label(result.phase_name, result.component)} of "
            + f"event {fmt_timestamp(result.event_time)}: {result.rows} initial "
            + f"pick(s) and {result.snapshots} snapshot(s) deleted, {picks(result)} "
            + f"dismissed.{kept(result)}"
        )

    def confirm(results: list[RemovePhaseResult]) -> bool:
        if dry_run:
            return False
        if len(results) == 1:
            (result,) = results
            question = (
                f"Remove phase {phase_label(result.phase_name, result.component)} "
                + f"of event {fmt_timestamp(result.event_time)}, with "
                + f"{result.rows} initial pick(s) and {result.snapshots} "
                + f"snapshot(s), and dismiss {picks(result)}?{kept(result)}"
            )
        else:
            first = results[0]
            question = (
                f"Remove phase {phase_label(first.phase_name, first.component)} "
                + f"of {len(results)} events, with "
                + f"{sum(r.rows for r in results)} initial pick(s) and "
                + f"{sum(r.snapshots for r in results)} snapshot(s), and dismiss "
                + f"{sum(r.dismissed_picks + r.dismissed_unmatched for r in results)}"
                + f" pick(s)?{kept_in_all(results)}"
            )
        confirm_or_abort(question, yes=yes)
        return True

    console = Console()
    for result in remove_phases(phase_ids, confirm=confirm):
        console.print(line(result))


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
    from aimbat.db import engine
    from aimbat.models import AimbatPhase

    phase_id = phase_parameters.phase_id()
    with Session(engine) as session:
        parameters = session.get_one(AimbatPhase, phase_id).parameters
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
    from aimbat.models import AimbatPhaseParameters, phase_label
    from aimbat.models._format import RichColSpec
    from aimbat.utils import uuid_shortener

    from .common import json_to_table

    raw = table_parameters.raw

    with Session(engine) as session:
        title, filter_id = _event_title(session, "Phase parameters", event_id, raw=raw)
        data = dump_phase_parameter_table(session, event_id=filter_id, name=phase)
        phase_names = {
            row["phase_id"]: phase_label(row["phase_name"], row["phase_component"])
            for row in data
        }

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
