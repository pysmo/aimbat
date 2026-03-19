"""View and manage snapshots of processing parameters.

A snapshot captures the current event and seismogram processing parameters
(e.g. time window, bandpass filter, picks) so they can be restored later.
Use `snapshot create` before making experimental changes, and `snapshot rollback`
to undo them if needed.
"""

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
    simple_exception,
)

app = App(name="snapshot", help=__doc__, help_format="markdown")


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


if __name__ == "__main__":
    app()
