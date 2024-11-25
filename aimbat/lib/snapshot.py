from aimbat.lib.common import ic
from aimbat.lib.db import engine
from aimbat.lib.event import get_active_event
from aimbat.lib.misc.rich_utils import make_table
from aimbat.lib.models import (
    # AimbatEvent,
    AimbatSnapshot,
    AimbatEventParameterSnapshot,
    AimbatSeismogramParameterSnapshot,
)
from sqlmodel import Session, select
from rich.console import Console


def create_snapshot(session: Session, comment: str | None = None) -> None:
    """Create a snapshot of the AIMBAT processing parameters.

    Parameters:
        session: SQL session.
        comment: Optional comment.
    """

    ic()
    ic(comment, engine)

    event = get_active_event(session)
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


def delete_snapshot(session: Session, snapshot_id: int) -> None:
    """Delete an AIMBAT parameter snapshot.

    Parameters:
        snapshot_id: Snapshot id.
    """

    ic()
    ic(snapshot_id, engine)

    select_snapshot = select(AimbatSnapshot).where(AimbatSnapshot.id == snapshot_id)
    snapshot = session.exec(select_snapshot).one_or_none()

    if not snapshot:
        raise RuntimeError(
            f"Unable to delete snapshot: snapshot with id={snapshot_id} not found."
        )

    session.delete(snapshot)
    session.commit()


def print_snapshot_table(session: Session, all_events: bool) -> None:
    """Print a pretty table with AIMBAT snapshots."""

    title = "AIMBAT snapshots for all events"
    aimbat_snapshots = None

    if all_events:
        aimbat_snapshots = session.exec(select(AimbatSnapshot)).all()
    else:
        active_event = get_active_event(session)
        aimbat_snapshots = active_event.snapshots
        title = f"AIMBAT snapshots for event {active_event.time} (ID={active_event.id})"

    table = make_table(title=title)

    table.add_column("id", justify="center", style="cyan", no_wrap=True)
    table.add_column("Date & Time", justify="center", style="cyan", no_wrap=True)
    table.add_column("Comment", justify="center", style="magenta")
    if all_events:
        table.add_column("Event ID", justify="center", style="magenta")
    table.add_column("# Seismograms", justify="center", style="green")

    for snapshot in aimbat_snapshots:
        if all_events:
            table.add_row(
                str(snapshot.id),
                str(snapshot.date),
                str(snapshot.comment),
                str(snapshot.event_id),
                str(len(snapshot.seismogram_parameter_snapshot)),
            )
        else:
            table.add_row(
                str(snapshot.id),
                str(snapshot.date),
                str(snapshot.comment),
                str(len(snapshot.seismogram_parameter_snapshot)),
            )

    console = Console()
    console.print(table)
