"""Actions that create, restore or delete snapshots."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Engine

from aimbat import core
from aimbat.core import RollbackResult
from aimbat.models import AimbatSnapshot

from ._session import open_session, require_ids

__all__ = ["create_snapshot", "delete_snapshots", "rollback_to_snapshot"]


def create_snapshot(
    phase_id: UUID,
    comment: str | None = None,
    *,
    engine: Engine | None = None,
) -> None:
    """Record the current parameters and quality values of a phase.

    Args:
        phase_id: ID of the phase.
        comment: Comment to store with the snapshot.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If the phase does not exist.
    """
    with open_session(engine) as session:
        core.create_snapshot(session, phase_id, comment)
        session.commit()


def rollback_to_snapshot(
    snapshot_id: UUID, *, engine: Engine | None = None
) -> RollbackResult:
    """Restore the parameters recorded in a snapshot as the live parameters.

    Seismograms added to the phase after the snapshot keep their parameters.

    Args:
        snapshot_id: ID of the snapshot.
        engine: Engine to use. Defaults to the project engine.

    Returns:
        The seismograms left as they are.

    Raises:
        ValueError: If the snapshot does not exist.
    """
    with open_session(engine) as session:
        result = core.rollback_to_snapshot(session, snapshot_id)
        session.commit()
    return result


def delete_snapshots(
    snapshot_ids: Sequence[UUID], *, engine: Engine | None = None
) -> None:
    """Delete snapshots.

    Args:
        snapshot_ids: IDs of the snapshots to delete.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not a snapshot. Nothing is deleted.
    """
    with open_session(engine) as session:
        for snapshot_id in require_ids(session, AimbatSnapshot, snapshot_ids):
            core.delete_snapshot(session, snapshot_id)
        session.commit()
