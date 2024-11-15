from aimbat.lib.common import cli_enable_debug
from aimbat.lib.db import engine
from aimbat.lib.models import (
    AimbatEvent,
    AimbatSnapshot,
    AimbatEventParameterSnapshot,
    AimbatSeismogramParameterSnapshot,
)
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from rich.console import Console
from rich.table import Table
from icecream import ic  # type: ignore
import click

ic.disable()


def snapshot_create(event_id: int, comment: str | None = None) -> None:
    """Create a snapshot of the AIMBAT processing parameters.

    Parameters:
        event_id: Event id.
        comment: Optional comment.
    """

    ic()
    ic(event_id, comment, engine)

    with Session(engine) as session:
        try:
            select_event = select(AimbatEvent).where(AimbatEvent.id == event_id)
            event = session.exec(select_event).one()
        except NoResultFound:
            raise RuntimeError(f"Unable to find event with id={event_id}.")

        snapshot = AimbatSnapshot(event_id=event.id, comment=comment)
        session.add(snapshot)

        event_parameter_snapshot = AimbatEventParameterSnapshot.model_validate(
            event.parameter, update={"id": None, "snapshot_id": snapshot.id}
        )
        session.add(event_parameter_snapshot)

        for seismogram in event.seismograms:
            seismogram_parameter_snapshot = (
                AimbatSeismogramParameterSnapshot.model_validate(
                    seismogram.parameter,
                    update={"id": None, "snapshot_id": snapshot.id},
                )
            )
            session.add(seismogram_parameter_snapshot)

        session.commit()


def snapshot_delete(snapshot_id: int) -> None:
    """Delete an AIMBAT parameter snapshot.

    Parameters:
        event_id: Event id.
    """

    ic()
    ic(snapshot_id, engine)

    with Session(engine) as session:
        try:
            select_snapshot = select(AimbatSnapshot).where(
                AimbatSnapshot.id == snapshot_id
            )
            snapshot = session.exec(select_snapshot).one()
        except NoResultFound:
            raise RuntimeError(f"Unable to find snapshot with id={snapshot_id}.")

        session.delete(snapshot)
        session.commit()


def print_table() -> None:
    """Print a pretty table with AIMBAT snapshots."""

    table = Table(title="AIMBAT Snapshots")

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Date & Time", justify="center", style="cyan", no_wrap=True)
    table.add_column("Comment", justify="center", style="magenta")
    table.add_column("Event ID", justify="center", style="magenta")
    table.add_column("# Seismograms", justify="center", style="green")

    with Session(engine) as session:
        all_snapshots = session.exec(select(AimbatSnapshot)).all()
        if all_snapshots is not None:
            for snapshot in all_snapshots:
                assert snapshot.id is not None
                table.add_row(
                    str(snapshot.id),
                    str(snapshot.date),
                    str(snapshot.comment),
                    str(snapshot.event_id),
                    str(len(snapshot.seismogram_parameter_snapshot)),
                )

    console = Console()
    console.print(table)


@click.group("snapshot")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """View and manage stations in the AIMBAT project."""
    cli_enable_debug(ctx)


@cli.command("create")
@click.argument("event_id", nargs=1, type=int, required=True)
@click.option("--comment", "-c", default=None, help="Add a comment to snapshot")
def cli_create(event_id: int, comment: str | None = None) -> None:
    """Create new snapshot."""
    snapshot_create(event_id, comment)


@cli.command("delete")
@click.argument("snapshot_id", nargs=1, type=int, required=True)
def cli_delete(snapshot_id: int) -> None:
    """Delete existing snapshot."""
    snapshot_delete(snapshot_id)


@cli.command("list")
def cli_list() -> None:
    """Print information on the snapshots stored in AIMBAT."""
    print_table()


if __name__ == "__main__":
    cli(obj={})
