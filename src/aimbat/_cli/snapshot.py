"""View and manage snapshots of processing parameters.

A snapshot captures the current processing parameters of one phase and of
its seismograms (e.g. time window, bandpass filter, picks) so they can be
restored later.
Use `snapshot create` before making experimental changes, and `snapshot rollback`
to undo them if needed.
"""

from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from cyclopts import App, Parameter, validators

from aimbat.models import AimbatSnapshot

from .common import (
    ConfirmParameters,
    DebugParameter,
    IccsPlotParameters,
    JsonDumpParameters,
    TableParameters,
    component_parameter,
    confirm_or_abort,
    event_parameter,
    event_parameter_is_all,
    event_parameter_with_all,
    handle_issues,
    id_label,
    id_parameter,
    make_note_app,
    phase_filter_parameter,
    phase_parameter,
    print_json_dump,
    print_quality_table,
    resolve_phase_option,
)

app = App(name="snapshot", help=__doc__, help_format="markdown")
_note = make_note_app(
    "snapshot",
    AimbatSnapshot,
    id_parameter(AimbatSnapshot, help="UUID (or unique prefix) of snapshot."),
)
_quality = App(
    name="quality", help="View snapshot quality metrics.", help_format="markdown"
)
app.command(_note)
app.command(_quality)


@app.command(name="create")
@handle_issues
def cli_snapshot_create(
    event_id: Annotated[UUID, event_parameter()],
    comment: str | None = None,
    *,
    phase: Annotated[str | None, phase_parameter()] = None,
    component: Annotated[str | None, component_parameter()] = None,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Create a new snapshot of current processing parameters.

    Saves the current parameters of a phase and of its seismograms so they
    can be restored later with `snapshot rollback`.

    Args:
        event_id: UUID (or unique prefix) of the event whose phase to snapshot.
        comment: Optional description to help identify this snapshot later.
        phase: Name of the phase to snapshot.
        component: Component of the phase to snapshot.
    """
    from aimbat.actions import create_snapshot

    create_snapshot(resolve_phase_option(event_id, phase, component), comment)


@app.command(name="rollback")
@handle_issues
def cli_snapshot_rollback(
    snapshot_id: Annotated[
        UUID,
        id_parameter(
            AimbatSnapshot,
            help="UUID (or unique prefix) of snapshot to use for rollback.",
        ),
    ],
    *,
    confirm: ConfirmParameters = ConfirmParameters(),
) -> None:
    """Restore saved parameters from a snapshot as the current live values.

    Overwrites the current parameters of the snapshot's phase and of its
    seismograms with those recorded in the snapshot. Other phases are
    unaffected. Any ICCS runs or parameter changes
    made after the snapshot was taken are undone. The snapshot itself is not
    deleted, so you can roll back to it again.

    If the snapshot has MCCC quality data, the live quality metrics are also
    restored from the best matching snapshot (same parameter hash, most recent
    MCCC run).

    Seismograms added after the snapshot was taken keep their parameters.
    """
    from rich.console import Console

    from aimbat.actions import rollback_to_snapshot

    confirm_or_abort(
        "Overwrite current live parameters with this snapshot?", yes=confirm.yes
    )
    result = rollback_to_snapshot(snapshot_id)
    if n := len(result.added_since):
        Console().print(
            f"{n} seismogram{'' if n == 1 else 's'} added since the snapshot "
            + f"{'is' if n == 1 else 'are'} kept as {'it is' if n == 1 else 'they are'}."
        )


@app.command(name="delete")
@handle_issues
def cli_snapshot_delete(
    snapshot_id: Annotated[
        UUID,
        id_parameter(
            AimbatSnapshot,
            help="UUID (or unique prefix) of snapshot to delete.",
        ),
    ],
    *,
    confirm: ConfirmParameters = ConfirmParameters(),
) -> None:
    """Delete an existing snapshot.

    Only removes the snapshot's frozen parameter and quality records;
    current phase and seismogram data are unaffected.
    """
    from aimbat.actions import delete_snapshots

    confirm_or_abort(f"Delete snapshot {snapshot_id}?", yes=confirm.yes)
    delete_snapshots([snapshot_id])


@app.command(name="dump")
@handle_issues
def cli_snapshot_dump(
    *,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Dump the contents of the AIMBAT snapshot tables to json."""
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import (
        dump_phase_parameter_snapshot_table,
        dump_phase_quality_snapshot_table,
        dump_seismogram_parameter_snapshot_table,
        dump_seismogram_quality_snapshot_table,
        dump_snapshot_table,
    )
    from aimbat.db import engine

    with Session(engine) as session:
        data = {
            "snapshots": dump_snapshot_table(
                session, by_alias=dump_parameters.by_alias
            ),
            "phase_parameters": dump_phase_parameter_snapshot_table(
                session, by_alias=dump_parameters.by_alias
            ),
            "seismogram_parameters": dump_seismogram_parameter_snapshot_table(
                session, by_alias=dump_parameters.by_alias
            ),
            "phase_quality": dump_phase_quality_snapshot_table(
                session, by_alias=dump_parameters.by_alias
            ),
            "seismogram_quality": dump_seismogram_quality_snapshot_table(
                session, by_alias=dump_parameters.by_alias
            ),
        }
        print_json(data=data)


@app.command(name="list")
@handle_issues
def cli_snapshot_list(
    event_id: Annotated[UUID | Literal["all"], event_parameter_with_all()],
    *,
    phase: Annotated[str | None, phase_filter_parameter()] = None,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Print information on the snapshots of an event's phases."""
    from sqlmodel import Session

    from aimbat.core import dump_snapshot_table, resolve_event
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.models import AimbatSnapshotRead
    from aimbat.utils import uuid_shortener

    from .common import json_to_table

    if raw := table_parameters.raw:
        exclude = {"short_id", "short_event_id"}
    else:
        exclude = {"id", "event_id"}

    with Session(engine) as session:
        logger.info("Printing AIMBAT snapshots table.")

        if event_parameter_is_all(event_id):
            event = None
            title = "AIMBAT snapshots for all events"
        else:
            event = resolve_event(session, event_id)
            if raw:
                time = event.time.isoformat()
                id = str(event.id)
                exclude.add("event_id")
            else:
                time = event.time.strftime("%Y-%m-%d %H:%M:%S")
                id = uuid_shortener(session, event)
                exclude.add("short_event_id")
            title = f"AIMBAT snapshots for event {time} (ID={id})"

        snapshot_data = dump_snapshot_table(
            session,
            from_read_model=True,
            event_id=event.id if event else None,
            exclude=exclude,
            phase_name=phase,
        )

        json_to_table(
            data=snapshot_data, model=AimbatSnapshotRead, title=title, raw=raw
        )


@app.command(name="preview")
@handle_issues
def cli_snapshot_preview(
    snapshot_id: Annotated[
        UUID,
        id_parameter(
            AimbatSnapshot, help="UUID (or unique prefix) of snapshot to preview."
        ),
    ],
    *,
    iccs_plot_parameters: IccsPlotParameters = IccsPlotParameters(),
    as_matrix: Annotated[bool, Parameter(name="matrix")] = False,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Preview the ICCS stack/matrix of a snapshot."""
    from sqlmodel import Session

    from aimbat.core import build_iccs_from_snapshot
    from aimbat.db import engine
    from aimbat.plot import plot_matrix_image, plot_stack

    with Session(engine) as session:
        iccs = build_iccs_from_snapshot(session, snapshot_id).iccs

    if as_matrix:
        plot_matrix_image(
            iccs,
            iccs_plot_parameters.context,
            all_seismograms=iccs_plot_parameters.all_seismograms,
            return_fig=False,
        )
    else:
        plot_stack(
            iccs,
            iccs_plot_parameters.context,
            all_seismograms=iccs_plot_parameters.all_seismograms,
            return_fig=False,
        )


@app.command(name="details")
@handle_issues
def cli_snapshot_details(
    snapshot_id: Annotated[
        UUID,
        id_parameter(
            AimbatSnapshot,
            help="UUID (or unique prefix) of snapshot to show details for.",
        ),
    ],
    *,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Print information on the phase parameters saved in a snapshot."""
    from sqlmodel import Session

    from aimbat.db import engine
    from aimbat.models import AimbatPhaseParametersSnapshot

    from .common import json_to_table

    with Session(engine) as session:
        snapshot = session.get(AimbatSnapshot, snapshot_id)

        if snapshot is None:
            raise ValueError(
                f"Unable to print snapshot parameters: snapshot with id={snapshot_id} not found."
            )

        raw = table_parameters.raw
        label = id_label(session, AimbatSnapshot, snapshot.id, raw=raw)
        title = f"Saved phase parameters in snapshot: {label}"

        parameters_snapshot = snapshot.phase_parameters_snapshot

        json_to_table(
            data=parameters_snapshot.model_dump(
                mode="json", exclude={"id", "snapshot_id", "parameters_id"}
            ),
            model=AimbatPhaseParametersSnapshot,
            title=title,
            key_header="Parameter",
        )


@_quality.command(name="dump")
@handle_issues
def cli_snapshot_quality_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump snapshot quality statistics to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.core import dump_snapshot_quality_table

    print_json_dump(dump_snapshot_quality_table, by_alias=dump_parameters.by_alias)


@_quality.command(name="list")
@handle_issues
def cli_snapshot_quality_list(
    event_id: Annotated[UUID | Literal["all"], event_parameter_with_all()],
    *,
    phase: Annotated[str | None, phase_filter_parameter()] = None,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Show aggregated quality statistics for snapshots of an event or all events.

    Displays ICCS and MCCC quality metrics (means, SEMs, RMSE) from the frozen
    quality records of each snapshot.
    """
    from sqlmodel import Session

    from aimbat.core import dump_snapshot_quality_table, resolve_event
    from aimbat.db import engine
    from aimbat.models import AimbatEvent

    raw = table_parameters.raw

    with Session(engine) as session:
        if event_parameter_is_all(event_id):
            title, filter_id = "Quality statistics for all snapshots", None
        else:
            event = resolve_event(session, event_id)
            label = id_label(session, AimbatEvent, event.id, raw=raw)
            title = f"Quality statistics for snapshots of event: {label}"
            filter_id = event.id

        print_quality_table(
            session,
            dump_snapshot_quality_table,
            title=title,
            filter_id=filter_id,
            id_field="event_id",
            id_columns={"event_id": AimbatEvent, "snapshot_id": AimbatSnapshot},
            raw=raw,
            filters={"phase_name": phase},
        )


@app.command(name="results")
@handle_issues
def cli_snapshot_results(
    snapshot_id: Annotated[
        UUID,
        id_parameter(AimbatSnapshot, help="UUID (or unique prefix) of snapshot."),
    ],
    *,
    output: Annotated[
        Path | None,
        Parameter(
            name="output",
            help="Write results to this JSON file instead of printing to stdout.",
            validator=validators.Path(dir_okay=False),
        ),
    ] = None,
    force: Annotated[
        bool,
        Parameter(help="Overwrite `--output` if it already exists."),
    ] = False,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Export per-seismogram MCCC results from a snapshot as JSON.

    Each row contains the frozen refined pick, ICCS correlation coefficient,
    per-seismogram MCCC quality metrics, and the MCCC RMSE of the phase.

    Results are printed to stdout unless `--output` is given, in which case
    they are written to the specified file.
    """
    import json

    from sqlmodel import Session

    from aimbat.core import dump_snapshot_results
    from aimbat.db import engine

    if output is not None and output.exists() and not force:
        raise FileExistsError(f"{output} already exists; pass --force to overwrite.")

    with Session(engine) as session:
        data = dump_snapshot_results(
            session,
            snapshot_id,
            by_alias=dump_parameters.by_alias,
        )

    if output is None:
        from rich import print_json

        print_json(data=data)
    else:
        output.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    app()
