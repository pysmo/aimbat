"""View and manage snapshots."""

from aimbat.lib.common import debug_callback
from typing import Annotated, Optional
import typer

from aimbat.lib.models import AimbatSnapshot


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


def _delete_snapshot(snapshot_id: int, db_url: str | None) -> None:
    from aimbat.lib.snapshot import delete_snapshot
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        delete_snapshot(session, snapshot_id)


def _print_snapshot_table(db_url: str | None, all_events: bool) -> None:
    from aimbat.lib.snapshot import print_snapshot_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_snapshot_table(session, all_events)


app = typer.Typer(
    name="snapshot",
    no_args_is_help=True,
    callback=debug_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)


@app.command("create")
def snapshot_cli_create(
    ctx: typer.Context,
    comment: Annotated[
        Optional[str], typer.Option(help="Create snapshot with optional comment.")
    ] = None,
) -> None:
    """Create new snapshot."""
    db_url = ctx.obj["DB_URL"]
    _create_snapshot(db_url=db_url, comment=comment)


@app.command("rollback")
def snapshot_cli_rollback(
    id: Annotated[int, typer.Argument(help="Snapshot ID Number.")],
    ctx: typer.Context,
) -> None:
    """Rollback to snapshot."""
    db_url = ctx.obj["DB_URL"]
    _rollback_to_snapshot(db_url=db_url, snapshot_id=id)


@app.command("delete")
def snapshot_cli_delete(
    ctx: typer.Context,
    id: Annotated[int, typer.Argument(help="Snapshot ID Number.")],
) -> None:
    """Delete existing snapshot."""
    db_url = ctx.obj["DB_URL"]
    _delete_snapshot(snapshot_id=id, db_url=db_url)


@app.command("list")
def snapshot_cli_list(
    ctx: typer.Context,
    all_events: Annotated[
        bool, typer.Option("--all", help="Select snapshots for all events.")
    ] = False,
) -> None:
    """Print information on the snapshots for the active event."""
    db_url = ctx.obj["DB_URL"]
    _print_snapshot_table(db_url, all_events)


if __name__ == "__main__":
    app()
