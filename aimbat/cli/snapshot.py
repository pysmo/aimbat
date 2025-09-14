"""View and manage snapshots."""

from aimbat.cli.common import CommonParameters
from aimbat.lib.models import AimbatSnapshot
from typing import Annotated
from cyclopts import App, Parameter


def _create_snapshot(db_url: str | None, comment: str | None = None) -> None:
    from aimbat.lib.snapshot import create_snapshot
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        create_snapshot(session, comment)


def _rollback_to_snapshot(db_url: str | None, snapshot_id: int) -> None:
    from aimbat.lib.snapshot import rollback_to_snapshot
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session, select

    with Session(engine_from_url(db_url)) as session:
        snapshot = session.exec(
            select(AimbatSnapshot).where(AimbatSnapshot.id == snapshot_id)
        ).one()
        rollback_to_snapshot(session, snapshot)


def _delete_snapshot(db_url: str | None, snapshot_id: int) -> None:
    from aimbat.lib.snapshot import delete_snapshot_by_id
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        delete_snapshot_by_id(session, snapshot_id)


def _print_snapshot_table(db_url: str | None, all_events: bool) -> None:
    from aimbat.lib.snapshot import print_snapshot_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_snapshot_table(session, all_events)


app = App(name="snapshot", help=__doc__, help_format="markdown")


@app.command(name="create")
def cli_snapshot_create(
    comment: str | None = None, *, common: CommonParameters | None = None
) -> None:
    """Create new snapshot.

    Parameters:
        comment: Create snapshot with optional comment.
    """

    common = common or CommonParameters()

    _create_snapshot(db_url=common.db_url, comment=comment)


@app.command(name="rollback")
def cli_snapshot_rollback(
    snapshot_id: Annotated[int, Parameter(name="id")],
    *,
    common: CommonParameters | None = None,
) -> None:
    """Rollback to snapshot.

    Parameters:
        snapshot_id: Snapshot ID Number.
    """

    common = common or CommonParameters()

    _rollback_to_snapshot(common.db_url, snapshot_id)


@app.command(name="delete")
def cli_snapshop_delete(
    snapshot_id: Annotated[int, Parameter(name="id")],
    *,
    common: CommonParameters | None = None,
) -> None:
    """Delete existing snapshot.

    Parameters:
        snapshot_id: Snapshot ID Number.
    """

    common = common or CommonParameters()

    _delete_snapshot(common.db_url, snapshot_id)


@app.command(name="list")
def cli_snapshot_list(
    *,
    all_events: Annotated[bool, Parameter("all")] = False,
    common: CommonParameters | None = None,
) -> None:
    """Print information on the snapshots for the active event.

    Parameters:
        all_events: Select snapshots for all events.
    """

    common = common or CommonParameters()

    _print_snapshot_table(common.db_url, all_events)


if __name__ == "__main__":
    app()
