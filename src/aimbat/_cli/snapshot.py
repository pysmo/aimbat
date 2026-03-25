"""View and manage snapshots of processing parameters.

A snapshot captures the current event and seismogram processing parameters
(e.g. time window, bandpass filter, picks) so they can be restored later.
Use `snapshot create` before making experimental changes, and `snapshot rollback`
to undo them if needed.
"""

from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from cyclopts import App, Parameter

from aimbat.models import AimbatSnapshot

from .common import (
    DebugParameter,
    IccsPlotParameters,
    JsonDumpParameters,
    TableParameters,
    event_parameter,
    event_parameter_is_all,
    event_parameter_with_all,
    id_parameter,
    open_in_editor,
    simple_exception,
)

app = App(name="snapshot", help=__doc__, help_format="markdown")
_note = App(name="note", help="Read and edit snapshot notes.", help_format="markdown")
_quality = App(
    name="quality", help="View snapshot quality metrics.", help_format="markdown"
)
app.command(_note)
app.command(_quality)


@_note.command(name="read")
@simple_exception
def cli_snapshot_note_read(
    snapshot_id: Annotated[
        UUID,
        id_parameter(AimbatSnapshot, help="UUID (or unique prefix) of snapshot."),
    ],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Display the note attached to a snapshot, rendered as Markdown."""
    from rich.console import Console
    from rich.markdown import Markdown
    from sqlmodel import Session

    from aimbat.core import get_note_content
    from aimbat.db import engine

    with Session(engine) as session:
        content = get_note_content(session, "snapshot", snapshot_id)

    Console().print(Markdown(content) if content else "(no note)")


@_note.command(name="edit")
@simple_exception
def cli_snapshot_note_edit(
    snapshot_id: Annotated[
        UUID,
        id_parameter(AimbatSnapshot, help="UUID (or unique prefix) of snapshot."),
    ],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Open the snapshot note in `$EDITOR` and save changes on exit."""
    from sqlmodel import Session

    from aimbat.core import get_note_content, save_note
    from aimbat.db import engine

    with Session(engine) as session:
        original = get_note_content(session, "snapshot", snapshot_id)

    updated = open_in_editor(original)

    if updated != original:
        with Session(engine) as session:
            save_note(session, "snapshot", snapshot_id, updated)


@app.command(name="create")
@simple_exception
def cli_snapshot_create(
    event_id: Annotated[UUID, event_parameter()],
    comment: str | None = None,
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Create a new snapshot of current processing parameters.

    Saves the current event and seismogram parameters for an event so
    they can be restored later with `snapshot rollback`.

    Args:
        comment: Optional description to help identify this snapshot later.
    """
    from sqlmodel import Session

    from aimbat.core import create_snapshot, resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        event = resolve_event(session, event_id)
        create_snapshot(session, event, comment)


@app.command(name="rollback")
@simple_exception
def cli_snapshot_rollback(
    snapshot_id: Annotated[
        UUID,
        id_parameter(
            AimbatSnapshot,
            help="UUID (or unique prefix) of snapshot to use for rollback.",
        ),
    ],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Rollback to snapshot."""
    from sqlmodel import Session

    from aimbat.core import rollback_to_snapshot
    from aimbat.db import engine

    with Session(engine) as session:
        rollback_to_snapshot(session, snapshot_id)


@app.command(name="delete")
@simple_exception
def cli_snapshot_delete(
    snapshot_id: Annotated[
        UUID,
        id_parameter(
            AimbatSnapshot,
            help="UUID (or unique prefix) of snapshot to delete.",
        ),
    ],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Delete existing snapshot."""
    from sqlmodel import Session

    from aimbat.core import delete_snapshot
    from aimbat.db import engine

    with Session(engine) as session:
        delete_snapshot(session, snapshot_id)


@app.command(name="dump")
@simple_exception
def cli_snapshot_dump(
    *,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Dump the contents of the AIMBAT snapshot tables to json."""
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import (
        dump_event_parameter_snapshot_table,
        dump_event_quality_snapshot_table,
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
            "event_parameters": dump_event_parameter_snapshot_table(
                session, by_alias=dump_parameters.by_alias
            ),
            "seismogram_parameters": dump_seismogram_parameter_snapshot_table(
                session, by_alias=dump_parameters.by_alias
            ),
            "event_quality": dump_event_quality_snapshot_table(
                session, by_alias=dump_parameters.by_alias
            ),
            "seismogram_quality": dump_seismogram_quality_snapshot_table(
                session, by_alias=dump_parameters.by_alias
            ),
        }
        print_json(data=data)


@app.command(name="list")
@simple_exception
def cli_snapshot_list(
    event_id: Annotated[UUID | Literal["all"], event_parameter_with_all()],
    *,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Print information on the snapshots for an event."""
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
        )

        json_to_table(
            data=snapshot_data, model=AimbatSnapshotRead, title=title, raw=raw
        )


@app.command(name="preview")
@simple_exception
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
@simple_exception
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
    """Print information on the event parameters saved in a snapshot."""
    from sqlmodel import Session

    from aimbat.db import engine
    from aimbat.models import AimbatEventParametersSnapshot
    from aimbat.utils import uuid_shortener

    from .common import json_to_table

    with Session(engine) as session:
        snapshot = session.get(AimbatSnapshot, snapshot_id)

        if snapshot is None:
            raise ValueError(
                f"Unable to print snapshot parameters: snapshot with id={snapshot_id} not found."
            )

        raw = table_parameters.raw

        if raw:
            title = f"Saved event parameters in snapshot: {snapshot.id}"
        else:
            title = f"Saved event parameters in snapshot: {uuid_shortener(session, snapshot)}"

        parameters_snapshot = snapshot.event_parameters_snapshot

        json_to_table(
            data=parameters_snapshot.model_dump(
                mode="json", exclude={"id", "snapshot_id", "parameters_id"}
            ),
            model=AimbatEventParametersSnapshot,
            title=title,
            key_header="Parameter",
        )


@_quality.command(name="dump")
@simple_exception
def cli_snapshot_quality_dump(
    *, dump_parameters: JsonDumpParameters = JsonDumpParameters()
) -> None:
    """Dump snapshot quality statistics to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_snapshot_quality_table
    from aimbat.db import engine

    with Session(engine) as session:
        data = dump_snapshot_quality_table(session, by_alias=dump_parameters.by_alias)

    print_json(data=data)


@_quality.command(name="list")
@simple_exception
def cli_snapshot_quality_list(
    event_id: Annotated[UUID | Literal["all"], event_parameter_with_all()],
    *,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Show aggregated quality statistics for snapshots of an event or all events.

    Displays ICCS and MCCC quality metrics (means, SEMs, RMSE) from the frozen
    quality records of each snapshot.
    """
    from sqlmodel import Session

    from aimbat.core import dump_snapshot_quality_table, resolve_event
    from aimbat.db import engine
    from aimbat.models import AimbatEvent, RichColSpec, SeismogramQualityStats
    from aimbat.utils import uuid_shortener

    from .common import json_to_table

    raw = table_parameters.raw

    with Session(engine) as session:
        if event_parameter_is_all(event_id):
            title = "Quality statistics for all snapshots"
            exclude = None
            filter_event_id = None
        else:
            event = resolve_event(session, event_id)
            label = str(event.id) if raw else uuid_shortener(session, event)
            title = f"Quality statistics for snapshots of event: {label}"
            exclude = {"event_id"}
            filter_event_id = event.id

        col_specs = {
            "event_id": RichColSpec(
                formatter=lambda x: uuid_shortener(session, AimbatEvent, str_uuid=x),
            ),
            "snapshot_id": RichColSpec(
                formatter=lambda x: uuid_shortener(session, AimbatSnapshot, str_uuid=x),
            ),
        }

        data = dump_snapshot_quality_table(
            session,
            event_id=filter_event_id,
            exclude=exclude,
        )

    json_to_table(
        data=data,
        model=SeismogramQualityStats,
        title=title,
        raw=raw,
        col_specs=col_specs,
    )


@app.command(name="results")
@simple_exception
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
        ),
    ] = None,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Export per-seismogram MCCC results from a snapshot as JSON.

    Each row contains the frozen pick time (T1), ICCS correlation coefficient,
    per-seismogram MCCC quality metrics, and the event-level MCCC RMSE.

    Results are printed to stdout unless `--output` is given, in which case
    they are written to the specified file.
    """
    import json

    from sqlmodel import Session

    from aimbat.core import dump_snapshot_results
    from aimbat.db import engine

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
