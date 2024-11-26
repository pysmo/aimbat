from typing import Sequence

from aimbat.lib.common import ic
from aimbat.lib.db import engine
from aimbat.lib.event import get_active_event
from aimbat.lib.misc.rich_utils import make_table
from aimbat.lib.models import (
    AimbatActiveEvent,
    AimbatSeismogramParametersBase,
    AimbatSnapshot,
    AimbatEvent,
    AimbatEventParametersBase,
    AimbatEventParameters,
    AimbatEventParametersSnapshot,
    AimbatSeismogramParametersSnapshot,
)
from sqlmodel import Session, select
from rich.console import Console


def create_snapshot(session: Session, comment: str | None = None) -> None:
    """Create a snapshot of the AIMBAT processing parameters.

    Parameters:
        session: Database session.
        comment: Optional comment.
    """

    ic()
    ic(f"creating snapshot with {comment=}")

    event = get_active_event(session)

    snapshot = AimbatSnapshot(comment=comment)
    session.add(snapshot)
    session.commit()

    event_parameters_snapshot = AimbatEventParametersSnapshot.model_validate(
        event.parameters,
        update={
            "id": None,
            "snapshot_id": snapshot.id,
            "parameters_id": event.parameters.id,
        },
    )
    session.add(event_parameters_snapshot)

    for seismogram in event.seismograms:
        seismogram_parameter_snapshot = (
            AimbatSeismogramParametersSnapshot.model_validate(
                seismogram.parameters,
                update={
                    "id": None,
                    "snapshot_id": snapshot.id,
                    "seismogram_parameters_id": seismogram.parameters.id,
                },
            )
        )
        session.add(seismogram_parameter_snapshot)

    session.commit()


def rollback_to_snapshot(session: Session, snapshot: AimbatSnapshot) -> None:
    """Rollback to an AIMBAT parameters snapshot.

    Parameters:
        snapshot: Snapshot.
    """

    ic()
    ic(session, snapshot)

    current_event_parameters = snapshot.event_parameters_snapshot.parameters
    rollback_event_parameters = AimbatEventParametersBase.model_validate(
        snapshot.event_parameters_snapshot
    )
    for parameter, value in rollback_event_parameters.__dict__.items():
        setattr(current_event_parameters, parameter, value)
    session.add(current_event_parameters)

    for seismogram_parameters_snapshot in snapshot.seismogram_parameters_snapshots:
        current_seismogram_parameters = seismogram_parameters_snapshot.parameters
        rollback_seismogram_parameters = AimbatSeismogramParametersBase.model_validate(
            seismogram_parameters_snapshot
        )
        for parameter, value in rollback_seismogram_parameters.__dict__.items():
            setattr(current_seismogram_parameters, parameter, value)
        session.add(current_seismogram_parameters)

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


def get_snapshots(
    session: Session, all_events: bool = False
) -> Sequence[AimbatSnapshot]:
    """Get the snapshots for the active avent.

    Parameters:
        session: Database session.
        all_events: Get the selected snapshots for all events.

    Returns: Snapshots.
    """

    ic()
    ic(session, all_events)

    if all_events:
        return session.exec(select(AimbatSnapshot)).all()

    select_active_event_snapshots = (
        select(AimbatSnapshot)
        .join(AimbatEventParametersSnapshot)
        .join(AimbatEventParameters)
        .join(AimbatEvent)
        .join(AimbatActiveEvent)
        # .where(AimbatEvent.is_active == 1)
    )
    return session.exec(select_active_event_snapshots).all()


def print_snapshot_table(session: Session, all_events: bool) -> None:
    """Print a pretty table with AIMBAT snapshots."""

    ic()
    ic(session, all_events)

    title = "AIMBAT snapshots for all events"
    aimbat_snapshots = get_snapshots(session, all_events)

    if not all_events:
        active_event = get_active_event(session)
        title = f"AIMBAT snapshots for event {active_event.time} (ID={active_event.id})"

    table = make_table(title=title)

    table.add_column("id", justify="right", style="cyan", no_wrap=True)
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
                str(snapshot.event_parameters_snapshot.parameters.event_id),
                str(len(snapshot.seismogram_parameters_snapshots)),
            )
        else:
            table.add_row(
                str(snapshot.id),
                str(snapshot.date),
                str(snapshot.comment),
                str(len(snapshot.seismogram_parameters_snapshots)),
            )

    console = Console()
    console.print(table)
