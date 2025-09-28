"""View and manage snapshots."""

from aimbat.cli.common import GlobalParameters, TableParameters, simple_exception
from typing import Annotated
from cyclopts import App, Parameter
import uuid


@simple_exception
def _create_snapshot(comment: str | None = None) -> None:
    from aimbat.lib.db import engine
    from aimbat.lib.snapshot import create_snapshot
    from sqlmodel import Session

    with Session(engine) as session:
        create_snapshot(session, comment)


@simple_exception
def _rollback_to_snapshot(snapshot_id: uuid.UUID | str) -> None:
    from aimbat.lib.common import string_to_uuid
    from aimbat.lib.db import engine
    from aimbat.lib.models import AimbatSnapshot
    from aimbat.lib.snapshot import rollback_to_snapshot_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        if not isinstance(snapshot_id, uuid.UUID):
            snapshot_id = string_to_uuid(session, snapshot_id, AimbatSnapshot)
        rollback_to_snapshot_by_id(session, snapshot_id)


@simple_exception
def _delete_snapshot(snapshot_id: uuid.UUID | str) -> None:
    from aimbat.lib.common import string_to_uuid
    from aimbat.lib.db import engine
    from aimbat.lib.models import AimbatSnapshot
    from aimbat.lib.snapshot import delete_snapshot_by_id
    from sqlmodel import Session

    with Session(engine) as session:
        if not isinstance(snapshot_id, uuid.UUID):
            snapshot_id = string_to_uuid(session, snapshot_id, AimbatSnapshot)
        delete_snapshot_by_id(session, snapshot_id)


@simple_exception
def _print_snapshot_table(short: bool, all_events: bool) -> None:
    from aimbat.lib.snapshot import print_snapshot_table

    print_snapshot_table(short, all_events)


app = App(name="snapshot", help=__doc__, help_format="markdown")


@app.command(name="create")
def cli_snapshot_create(
    comment: str | None = None, *, global_parameters: GlobalParameters | None = None
) -> None:
    """Create new snapshot.

    Parameters:
        comment: Create snapshot with optional comment.
    """

    global_parameters = global_parameters or GlobalParameters()

    _create_snapshot(comment=comment)


@app.command(name="rollback")
def cli_snapshot_rollback(
    snapshot_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_paramaters: GlobalParameters | None = None,
) -> None:
    """Rollback to snapshot.

    Parameters:
        snapshot_id: Snapshot ID Number.
    """

    global_paramaters = global_paramaters or GlobalParameters()

    _rollback_to_snapshot(snapshot_id)


@app.command(name="delete")
def cli_snapshop_delete(
    snapshot_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Delete existing snapshot.

    Parameters:
        snapshot_id: Snapshot ID Number.
    """

    global_parameters = global_parameters or GlobalParameters()

    _delete_snapshot(snapshot_id)


@app.command(name="list")
def cli_snapshot_list(
    *,
    all_events: Annotated[bool, Parameter("all")] = False,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print information on the snapshots for the active event.

    Parameters:
        all_events: Select snapshots for all events.
    """

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    _print_snapshot_table(table_parameters.short, all_events)


if __name__ == "__main__":
    app()
