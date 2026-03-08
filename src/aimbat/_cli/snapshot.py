"""View and manage snapshots of processing parameters.

A snapshot captures the current event and seismogram processing parameters
(e.g. time window, bandpass filter, picks) so they can be restored later.
Use `snapshot create` before making experimental changes, and `snapshot rollback`
to undo them if needed.
"""

import uuid
from typing import Annotated

from cyclopts import App, Parameter

from aimbat.models import AimbatSnapshot

from .common import (
    ALL_EVENTS_PARAMETER,
    DebugParameter,
    GlobalParameters,
    IccsPlotParameters,
    TableParameters,
    id_parameter,
    simple_exception,
)

app = App(name="snapshot", help=__doc__, help_format="markdown")


@app.command(name="create")
@simple_exception
def cli_snapshot_create(
    comment: str | None = None,
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
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
        event = resolve_event(session, global_parameters.event_id)
        create_snapshot(session, event, comment)


@app.command(name="rollback")
@simple_exception
def cli_snapshot_rollback(
    snapshot_id: Annotated[uuid.UUID, id_parameter(AimbatSnapshot)],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Rollback to snapshot."""
    from sqlmodel import Session

    from aimbat.core import rollback_to_snapshot_by_id
    from aimbat.db import engine

    with Session(engine) as session:
        rollback_to_snapshot_by_id(session, snapshot_id)


@app.command(name="delete")
@simple_exception
def cli_snapshot_delete(
    snapshot_id: Annotated[uuid.UUID, id_parameter(AimbatSnapshot)],
    *,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Delete existing snapshot."""
    from sqlmodel import Session

    from aimbat.core import delete_snapshot_by_id
    from aimbat.db import engine

    with Session(engine) as session:
        delete_snapshot_by_id(session, snapshot_id)


@app.command(name="dump")
@simple_exception
def cli_snapshot_dump(
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump the contents of the AIMBAT snapshot table to json."""
    from rich import print_json
    from sqlmodel import Session

    from aimbat.core import dump_snapshot_tables_to_json, resolve_event
    from aimbat.db import engine

    with Session(engine) as session:
        event = (
            resolve_event(session, global_parameters.event_id)
            if not all_events
            else None
        )
        print_json(
            dump_snapshot_tables_to_json(
                session, all_events, as_string=True, event=event
            )
        )


@app.command(name="list")
@simple_exception
def cli_snapshot_list(
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print information on the snapshots for an event."""
    from pandas import Timestamp
    from sqlmodel import Session

    from aimbat.core import dump_snapshot_tables_to_json, resolve_event
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.models import AimbatEvent
    from aimbat.utils import TABLE_STYLING, json_to_table, uuid_shortener

    short = table_parameters.short

    with Session(engine) as session:
        logger.info("Printing AIMBAT snapshots table.")

        title = "AIMBAT snapshots for all events"

        event = None
        if not all_events:
            event = resolve_event(session, global_parameters.event_id)
            if short:
                title = f"AIMBAT snapshots for event {event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_shortener(session, event)})"
            else:
                title = f"AIMBAT snapshots for event {event.time} (ID={event.id})"

        data = dump_snapshot_tables_to_json(
            session, all_events, as_string=False, event=event
        )
        snapshot_data = data["snapshots"]

        column_order = ["id", "date", "comment", "seismogram_count"]
        if all_events:
            column_order.append("event_id")

        skip_keys = [] if all_events else ["event_id"]

        json_to_table(
            data=snapshot_data,
            title=title,
            column_order=column_order,
            skip_keys=skip_keys,
            formatters={
                "id": lambda x: (
                    uuid_shortener(session, AimbatSnapshot, str_uuid=x) if short else x
                ),
                "date": lambda x: TABLE_STYLING.timestamp_formatter(
                    Timestamp(x), short
                ),
                "event_id": lambda x: (
                    uuid_shortener(session, AimbatEvent, str_uuid=x) if short else x
                ),
            },
            common_column_kwargs={"justify": "center"},
            column_kwargs={
                "id": {
                    "header": "ID (shortened)" if short else "ID",
                    "style": TABLE_STYLING.id,
                    "no_wrap": True,
                },
                "date": {
                    "header": "Date & Time",
                    "style": TABLE_STYLING.mine,
                    "no_wrap": True,
                },
                "comment": {"style": TABLE_STYLING.mine},
                "seismogram_count": {
                    "header": "# Seismograms",
                    "style": TABLE_STYLING.linked,
                },
                "selected_seismogram_count": {
                    "header": "# Selected",
                    "style": TABLE_STYLING.linked,
                },
                "flipped_seismogram_count": {
                    "header": "# Flipped",
                    "style": TABLE_STYLING.linked,
                },
                "event_id": {
                    "header": "Event ID (shortened)" if short else "Event ID",
                    "style": TABLE_STYLING.linked,
                },
            },
        )


@app.command(name="preview")
@simple_exception
def cli_snapshot_preview(
    snapshot_id: Annotated[uuid.UUID, id_parameter(AimbatSnapshot)],
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
    snapshot_id: Annotated[uuid.UUID, id_parameter(AimbatSnapshot)],
    *,
    table_parameters: TableParameters = TableParameters(),
    _: DebugParameter = DebugParameter(),
) -> None:
    """Print information on the event parameters saved in a snapshot."""
    from sqlmodel import Session

    from aimbat.db import engine
    from aimbat.utils import TABLE_STYLING, json_to_table, uuid_shortener

    short = table_parameters.short

    with Session(engine) as session:
        snapshot = session.get(AimbatSnapshot, snapshot_id)

        if snapshot is None:
            raise ValueError(
                f"Unable to print snapshot parameters: snapshot with id={snapshot_id} not found."
            )

        parameters_snapshot = snapshot.event_parameters_snapshot
        json_to_table(
            data=parameters_snapshot.model_dump(mode="json"),
            title=f"Saved event parameters in snapshot: {uuid_shortener(session, parameters_snapshot.snapshot) if short else str(parameters_snapshot.snapshot.id)}",
            skip_keys=["id", "snapshot_id", "parameters_id"],
            common_column_kwargs={"highlight": True},
            column_kwargs={
                "Key": {
                    "header": "Parameter",
                    "justify": "left",
                    "style": TABLE_STYLING.id,
                },
            },
        )


if __name__ == "__main__":
    app()
