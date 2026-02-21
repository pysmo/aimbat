"""View and manage snapshots."""

from ._common import GlobalParameters, TableParameters, simple_exception
from typing import Annotated
from cyclopts import App, Parameter
import uuid

app = App(name="snapshot", help=__doc__, help_format="markdown")


@app.command(name="create")
@simple_exception
def cli_snapshot_create(
    comment: str | None = None, *, global_parameters: GlobalParameters | None = None
) -> None:
    """Create new snapshot.

    Args:
        comment: Create snapshot with optional comment.
    """
    from aimbat.db import engine
    from aimbat.core import create_snapshot
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        create_snapshot(session, comment)


@app.command(name="rollback")
@simple_exception
def cli_snapshot_rollback(
    snapshot_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_paramaters: GlobalParameters | None = None,
) -> None:
    """Rollback to snapshot.

    Args:
        snapshot_id: Snapshot ID Number.
    """
    from aimbat.utils import string_to_uuid
    from aimbat.db import engine
    from aimbat.models import AimbatSnapshot
    from aimbat.core import rollback_to_snapshot_by_id
    from sqlmodel import Session

    global_paramaters = global_paramaters or GlobalParameters()

    with Session(engine) as session:
        if not isinstance(snapshot_id, uuid.UUID):
            snapshot_id = string_to_uuid(session, snapshot_id, AimbatSnapshot)
        rollback_to_snapshot_by_id(session, snapshot_id)


@app.command(name="delete")
@simple_exception
def cli_snapshop_delete(
    snapshot_id: Annotated[uuid.UUID | str, Parameter(name="id")],
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Delete existing snapshot.

    Args:
        snapshot_id: Snapshot ID Number.
    """
    from aimbat.db import engine
    from aimbat.utils import string_to_uuid
    from aimbat.models import AimbatSnapshot
    from aimbat.core import delete_snapshot_by_id
    from sqlmodel import Session

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        if not isinstance(snapshot_id, uuid.UUID):
            snapshot_id = string_to_uuid(session, snapshot_id, AimbatSnapshot)
        delete_snapshot_by_id(session, snapshot_id)


@app.command(name="dump")
@simple_exception
def cli_snapshot_dump(
    all_events: Annotated[bool, Parameter("all")] = False,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Dump the contents of the AIMBAT snapshot table to json.

    Args:
        all_events: Select snapshots for all events.
    """
    from aimbat.db import engine
    from aimbat.core import dump_snapshot_table_to_json
    from sqlmodel import Session
    from rich import print_json

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_json(dump_snapshot_table_to_json(session, all_events, as_string=True))


@app.command(name="list")
@simple_exception
def cli_snapshot_list(
    all_events: Annotated[bool, Parameter("all")] = False,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print information on the snapshots for the active event.

    Args:
        all_events: Select snapshots for all events.
    """
    from aimbat.db import engine
    from aimbat.core import print_snapshot_table
    from sqlmodel import Session

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_snapshot_table(session, table_parameters.short, all_events)


if __name__ == "__main__":
    app()
