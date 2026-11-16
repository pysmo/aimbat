"""Actions that modify seismograms."""

from collections.abc import Mapping, Sequence
from uuid import UUID

from pandas import Timestamp
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import select

from aimbat import core
from aimbat.models import AimbatSeismogram
from aimbat.types import SeismogramParameter

from ._session import discard_cached_iccs_on_failure, open_session, require_ids

__all__ = [
    "delete_seismograms",
    "reset_seismogram_parameters",
    "set_picks",
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
    seismogram_ids: Sequence[UUID],
    values: Mapping[SeismogramParameter, Timestamp | bool | str],
    *,
    engine: Engine | None = None,
) -> None:
    """Set the same parameter values on several seismograms.

    Args:
        seismogram_ids: IDs of the seismograms to update.
        values: New value for each parameter, keyed by parameter name.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram. Nothing is
            changed.
        ValidationError: If any value is invalid. Nothing is changed.
    """
    with open_session(engine) as session:
        core.set_seismogram_parameters(session, seismogram_ids, values)
        session.commit()


def set_picks(
    event_id: UUID,
    picks: Mapping[UUID, Timestamp],
    *,
    engine: Engine | None = None,
) -> None:
    """Set the refined picks (`t1`) of seismograms of an event.

    Args:
        event_id: ID of the event the seismograms belong to.
        picks: New refined pick for each seismogram, keyed by seismogram ID.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram of the event.
            Nothing is changed.
        ValidationError: If any pick is invalid. Nothing is changed.
    """
    with discard_cached_iccs_on_failure(event_id), open_session(engine) as session:
        in_event = set(
            session.exec(
                select(AimbatSeismogram.id).where(AimbatSeismogram.event_id == event_id)
            ).all()
        )
        missing = [i for i in picks if i not in in_event]
        if missing:
            noun = "ID" if len(missing) == 1 else "IDs"
            raise NoResultFound(
                f"No seismogram of event {event_id} found with {noun} "
                + ", ".join(map(str, missing))
                + "."
            )
        core.set_seismogram_picks(session, picks)
        session.commit()


def reset_seismogram_parameters(
    seismogram_ids: Sequence[UUID], *, engine: Engine | None = None
) -> None:
    """Reset the parameters of several seismograms to their default values.

    This includes `t1`, so any refined pick is discarded.

    Args:
        seismogram_ids: IDs of the seismograms to reset.
        engine: Engine to use. Defaults to the project engine.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram. Nothing is
            changed.
    """
    with open_session(engine) as session:
        for seismogram_id in require_ids(session, AimbatSeismogram, seismogram_ids):
            core.reset_seismogram_parameters(session, seismogram_id)
        session.commit()
