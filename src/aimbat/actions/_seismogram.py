"""Actions that modify seismograms."""

from collections.abc import Mapping, Sequence
from uuid import UUID

from pandas import Timestamp
from sqlalchemy import Engine

from aimbat import core
from aimbat.models import AimbatSeismogram
from aimbat.types import SeismogramParameter

from ._session import discard_cached_iccs_on_failure, open_session, require_ids

__all__ = [
    "delete_seismograms",
    "reset_seismogram_parameters",
    "set_refined_picks",
    "set_seismogram_parameters",
]


def delete_seismograms(
    seismogram_ids: Sequence[UUID], *, engine: Engine | None = None
) -> None:
    """Delete seismograms, together with their parameters and quality values.

    Args:
        seismogram_ids: IDs of the seismograms to delete.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram. Nothing is
            deleted.
    """
    with open_session(engine) as session:
        for seismogram_id in require_ids(session, AimbatSeismogram, seismogram_ids):
            core.delete_seismogram(session, seismogram_id)
        session.commit()


def set_seismogram_parameters(
    phase_id: UUID,
    seismogram_ids: Sequence[UUID],
    values: Mapping[SeismogramParameter, Timestamp | bool | str],
    *,
    engine: Engine | None = None,
) -> None:
    """Set the same parameter values on several seismograms of a phase.

    Args:
        phase_id: ID of the phase.
        seismogram_ids: IDs of the seismograms to update.
        values: New value for each parameter, keyed by parameter name.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram of the phase.
            Nothing is changed.
        ValidationError: If any value is invalid. Nothing is changed.
    """
    with open_session(engine) as session:
        core.set_seismogram_parameters(session, phase_id, seismogram_ids, values)
        session.commit()


def set_refined_picks(
    phase_id: UUID,
    picks: Mapping[UUID, Timestamp],
    *,
    engine: Engine | None = None,
) -> None:
    """Set the refined picks of seismograms of a phase.

    Args:
        phase_id: ID of the phase.
        picks: New refined pick for each seismogram, keyed by seismogram ID.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram of the phase.
            Nothing is changed.
        ValidationError: If any pick is invalid. Nothing is changed.
    """
    with discard_cached_iccs_on_failure(phase_id), open_session(engine) as session:
        core.set_refined_picks(session, phase_id, picks)
        session.commit()


def reset_seismogram_parameters(
    phase_id: UUID, seismogram_ids: Sequence[UUID], *, engine: Engine | None = None
) -> None:
    """Reset the parameters of several seismograms of a phase to their defaults.

    This includes `refined_pick`, so any refined pick is discarded.

    Args:
        phase_id: ID of the phase.
        seismogram_ids: IDs of the seismograms to reset.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram of the phase.
            Nothing is changed.
    """
    with open_session(engine) as session:
        for seismogram_id in require_ids(session, AimbatSeismogram, seismogram_ids):
            core.reset_seismogram_parameters(session, phase_id, seismogram_id)
        session.commit()
