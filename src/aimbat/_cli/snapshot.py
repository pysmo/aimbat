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
    from aimbat.core import create_snapshot
    from sqlmodel import Session

    with Session(engine) as session:
        create_snapshot(session, comment)


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
    from aimbat.core import dump_snapshot_tables_to_json
    from sqlmodel import Session
    from rich import print_json

    with Session(engine) as session:
        print_json(dump_snapshot_tables_to_json(session, all_events, as_string=True))


@app.command(name="list")
@simple_exception
def cli_snapshot_list(
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print information on the snapshots for the active event."""
    from aimbat.db import engine
    from aimbat.core import print_snapshot_table
    from sqlmodel import Session

    with Session(engine) as session:
        print_snapshot_table(session, table_parameters.short, all_events)


@app.command(name="details")
@simple_exception
def cli_snapshot_details(
    snapshot_id: Annotated[uuid.UUID, id_parameter(AimbatSnapshot)],
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print information on the event parameters saved in a snapshot."""
    from aimbat.db import engine
    from aimbat.core import print_snapshot_parameters_table_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        print_snapshot_parameters_table_by_id(
            session, snapshot_id, table_parameters.short
        )


if __name__ == "__main__":
    app()
