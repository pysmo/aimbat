"""View and manage snapshots of processing parameters.

A snapshot captures the current event and seismogram processing parameters
(e.g. time window, bandpass filter, picks) so they can be restored later.
Use `snapshot create` before making experimental changes, and `snapshot rollback`
to undo them if needed.
"""

from .common import (
    GlobalParameters,
    TableParameters,
    simple_exception,
    id_parameter,
    ALL_EVENTS_PARAMETER,
)
from aimbat.models import AimbatSnapshot
from typing import Annotated
from cyclopts import App
import uuid

app = App(name="snapshot", help=__doc__, help_format="markdown")


@app.command(name="create")
@simple_exception
def cli_snapshot_create(
    comment: str | None = None,
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Create a new snapshot of current processing parameters.

    Saves the current event and seismogram parameters for the active event so
    they can be restored later with `snapshot rollback`.

    Args:
        comment: Optional description to help identify this snapshot later.
    """
    from aimbat.db import engine
    from aimbat.core import create_snapshot, get_active_event
    from sqlmodel import Session

    with Session(engine) as session:
        active_event = get_active_event(session)
        create_snapshot(session, active_event, comment)


@app.command(name="rollback")
@simple_exception
def cli_snapshot_rollback(
    snapshot_id: Annotated[uuid.UUID, id_parameter(AimbatSnapshot)],
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Rollback to snapshot."""
    from aimbat.db import engine
    from aimbat.core import rollback_to_snapshot_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        rollback_to_snapshot_by_id(session, snapshot_id)


@app.command(name="delete")
@simple_exception
def cli_snapshop_delete(
    snapshot_id: Annotated[uuid.UUID, id_parameter(AimbatSnapshot)],
    *,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Delete existing snapshot."""
    from aimbat.db import engine
    from aimbat.core import delete_snapshot_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        delete_snapshot_by_id(session, snapshot_id)


@app.command(name="dump")
@simple_exception
def cli_snapshot_dump(
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump the contents of the AIMBAT snapshot table to json."""
    from aimbat.db import engine
    from aimbat.core import dump_snapshot_tables_to_json, get_active_event
    from sqlmodel import Session
    from rich import print_json

    with Session(engine) as session:
        active_event = get_active_event(session) if not all_events else None
        print_json(
            dump_snapshot_tables_to_json(
                session, all_events, as_string=True, event=active_event
            )
        )


@app.command(name="list")
@simple_exception
def cli_snapshot_list(
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print information on the snapshots for the active event."""
    from aimbat.db import engine
    from aimbat.core import get_active_event, dump_snapshot_tables_to_json
    from aimbat.utils import uuid_shortener, json_to_table, TABLE_STYLING
    from aimbat.logger import logger
    from aimbat.models import AimbatEvent
    from pandas import Timestamp
    from sqlmodel import Session

    short = table_parameters.short

    with Session(engine) as session:
        logger.info("Printing AIMBAT snapshots table.")

        title = "AIMBAT snapshots for all events"

        active_event = None
        if not all_events:
            active_event = get_active_event(session)
            if short:
                title = f"AIMBAT snapshots for event {active_event.time.strftime('%Y-%m-%d %H:%M:%S')} (ID={uuid_shortener(session, active_event)})"
            else:
                title = f"AIMBAT snapshots for event {active_event.time} (ID={active_event.id})"

        data = dump_snapshot_tables_to_json(
            session, all_events, as_string=False, event=active_event
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


@app.command(name="details")
@simple_exception
def cli_snapshot_details(
    snapshot_id: Annotated[uuid.UUID, id_parameter(AimbatSnapshot)],
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print information on the event parameters saved in a snapshot."""
    from aimbat.db import engine
    from aimbat.utils import uuid_shortener, json_to_table, TABLE_STYLING
    from sqlmodel import Session

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
