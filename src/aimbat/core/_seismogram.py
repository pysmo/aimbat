"""Query, update, and delete AimbatSeismogram records and their processing parameters."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal, overload
from uuid import UUID

from pandas import Timestamp
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersBase,
    AimbatSeismogramRead,
)
from aimbat.types import SeismogramParameter
from aimbat.utils import check_field_name_flags, dump_models, rel

from ._session import flush_deletes
from ._validity import Validity

__all__ = [
    "delete_seismogram",
    "dump_seismogram_parameter_table",
    "dump_seismogram_table",
    "get_selected_seismograms",
    "reset_seismogram_parameters",
    "set_seismogram_parameter",
    "set_seismogram_parameters",
    "set_seismogram_picks",
]

type SeismogramParameterBool = Literal[
    SeismogramParameter.SELECT, SeismogramParameter.FLIP
]
type SeismogramParameterTimestamp = Literal[SeismogramParameter.T1]


def delete_seismogram(session: Session, seismogram_id: UUID) -> None:
    """Delete an AimbatSeismogram from the database.

    Args:
        session: Database session.
        seismogram_id: Seismogram ID.

    Raises:
        NoResultFound: If no seismogram with the given ID is found.
    """

    logger.info(f"Deleting seismogram {seismogram_id}.")

    seismogram = session.get(AimbatSeismogram, seismogram_id)
    if seismogram is None:
        raise NoResultFound(f"No AimbatSeismogram found with {seismogram_id=}")

    session.delete(seismogram)
    flush_deletes(session)


def dump_seismogram_table(
    session: Session,
    from_read_model: bool = False,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Dump the AimbatSeismogram table to json serialisable list of dicts.

    Args:
        session: Database session.
        from_read_model: Whether to dump from the read model (True) or the ORM model.
        by_alias: Whether to use serialisation aliases for the field names in the output.
        by_title: Whether to use titles for the field names in the output (only
            applicable when from_read_model is True). Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event ID to filter seismograms by (if none is provided,
            seismograms for all events are dumped).

    Returns:
        List of dicts representing the seismograms, built from the read
        model when `from_read_model` is True or from the ORM model otherwise.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
        ValueError: If `by_title` is True but `from_read_model` is False.
    """
    logger.debug("Dumping AIMBAT seismogram table to json.")

    check_field_name_flags(by_alias, by_title, from_read_model)

    if event_id is not None:
        statement = select(AimbatSeismogram).where(
            AimbatSeismogram.event_id == event_id
        )
    else:
        statement = select(AimbatSeismogram)

    statement = statement.options(
        selectinload(rel(AimbatSeismogram.station)),
        selectinload(rel(AimbatSeismogram.event)),
        selectinload(rel(AimbatSeismogram.parameters)),
        selectinload(rel(AimbatSeismogram.quality)),
    )

    seismograms = session.exec(statement).all()

    if from_read_model:
        validity = Validity.read(session, event_id)
        seismogram_reads = [
            AimbatSeismogramRead.from_seismogram(s, validity, session=session)
            for s in seismograms
        ]
        return dump_models(
            seismogram_reads,
            AimbatSeismogramRead,
            by_alias=by_alias,
            by_title=by_title,
            exclude=exclude,
        )

    return dump_models(
        seismograms, AimbatSeismogram, by_alias=by_alias, exclude=exclude
    )


def reset_seismogram_parameters(session: Session, seismogram_id: UUID) -> None:
    """Reset an AimbatSeismogram's parameters to their default values.

    All fields defined on AimbatSeismogramParametersBase are reset to the
    values produced by a fresh default instance, so newly added fields are
    picked up automatically. This includes `t1`, so a manual pick is
    discarded along with `select` and `flip`.

    Args:
        session: Database session.
        seismogram_id: ID of seismogram to reset parameters for.

    Raises:
        NoResultFound: If no seismogram with the given ID is found.
    """

    logger.info(f"Resetting parameters for seismogram {seismogram_id}.")

    seismogram = session.exec(
        select(AimbatSeismogram)
        .where(AimbatSeismogram.id == seismogram_id)
        .options(
            selectinload(rel(AimbatSeismogram.parameters)),
            selectinload(rel(AimbatSeismogram.event)).options(
                selectinload(rel(AimbatEvent.parameters)),
                selectinload(rel(AimbatEvent.seismograms)).selectinload(
                    rel(AimbatSeismogram.parameters)
                ),
            ),
        )
    ).one_or_none()
    if seismogram is None:
        raise NoResultFound(f"No AimbatSeismogram found with {seismogram_id=}")

    from ._snapshot import resync_quality

    defaults = AimbatSeismogramParametersBase()
    for field_name in AimbatSeismogramParametersBase.model_fields:
        setattr(seismogram.parameters, field_name, getattr(defaults, field_name))
    session.add(seismogram)
    resync_quality(session, seismogram.event)


@overload
def set_seismogram_parameter(
    session: Session,
    seismogram_id: UUID,
    name: SeismogramParameterBool,
    value: bool | str,
) -> None: ...


@overload
def set_seismogram_parameter(
    session: Session,
    seismogram_id: UUID,
    name: SeismogramParameterTimestamp,
    value: Timestamp,
) -> None: ...


@overload
def set_seismogram_parameter(
    session: Session,
    seismogram_id: UUID,
    name: SeismogramParameter,
    value: Timestamp | bool | str,
) -> None: ...


def set_seismogram_parameter(
    session: Session,
    seismogram_id: UUID,
    name: SeismogramParameter,
    value: Timestamp | bool | str,
) -> None:
    """Set parameter value for an AimbatSeismogram instance.

    Args:
        session: Database session
        seismogram_id: Seismogram id.
        name: Name of the parameter.
        value: Value to set parameter to.

    Raises:
        ValueError: If no seismogram with the given ID is found.
        ValidationError: If `value` fails Pydantic validation for `name`.
    """
    from ._snapshot import resync_quality

    logger.debug(
        f"Setting seismogram {name=} to {value=} in seismogram {seismogram_id=}."
    )

    seismogram = session.exec(
        select(AimbatSeismogram)
        .where(AimbatSeismogram.id == seismogram_id)
        .options(
            selectinload(rel(AimbatSeismogram.parameters)),
            selectinload(rel(AimbatSeismogram.event)).options(
                selectinload(rel(AimbatEvent.parameters)),
                selectinload(rel(AimbatEvent.seismograms)).selectinload(
                    rel(AimbatSeismogram.parameters)
                ),
            ),
        )
    ).one_or_none()
    if seismogram is None:
        raise ValueError(f"No AimbatSeismogram found with {seismogram_id=}")

    parameters = AimbatSeismogramParametersBase.model_validate(
        seismogram.parameters, update={name: value}
    )
    setattr(seismogram.parameters, name, getattr(parameters, name))
    session.add(seismogram)
    resync_quality(session, seismogram.event)


def set_seismogram_parameters(
    session: Session,
    seismogram_ids: Sequence[UUID],
    values: Mapping[SeismogramParameter, Timestamp | bool | str],
) -> None:
    """Set the same parameter values on several seismograms at once.

    Every seismogram and value is checked before anything changes, so an
    unknown ID or an invalid value leaves all seismograms as they were. The
    seismograms may belong to different events.

    Args:
        session: Database session.
        seismogram_ids: IDs of the seismograms to update. Duplicates are
            ignored. An empty sequence is a no-op.
        values: New value for each parameter, keyed by parameter name. An
            empty mapping is a no-op.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram.
        ValidationError: If any value fails Pydantic validation.
    """
    updates = {str(name): value for name, value in values.items()}
    logger.debug(f"Setting {updates} for {len(seismogram_ids)} seismogram(s).")
    _update_seismograms(session, dict.fromkeys(seismogram_ids, updates))


def set_seismogram_picks(session: Session, picks: Mapping[UUID, Timestamp]) -> None:
    """Set the refined pick (`t1`) of several seismograms, each to its own value.

    Every seismogram and pick is checked before anything changes, so an
    unknown ID or an invalid pick leaves all seismograms as they were. The
    seismograms may belong to different events.

    Args:
        session: Database session.
        picks: New refined pick for each seismogram, keyed by seismogram ID.
            An empty mapping is a no-op.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram.
        ValidationError: If any pick fails Pydantic validation.
    """
    logger.debug(f"Setting t1 for {len(picks)} seismogram(s).")
    _update_seismograms(
        session,
        {
            seismogram_id: {str(SeismogramParameter.T1): pick}
            for seismogram_id, pick in picks.items()
        },
    )


def _update_seismograms(
    session: Session, updates: Mapping[UUID, Mapping[str, Timestamp | bool | str]]
) -> None:
    """Apply per-seismogram parameter updates after validating all of them."""
    from ._snapshot import resync_quality

    ids = list(updates)

    seismograms = session.exec(
        select(AimbatSeismogram)
        .where(col(AimbatSeismogram.id).in_(ids))
        .options(
            selectinload(rel(AimbatSeismogram.parameters)),
            selectinload(rel(AimbatSeismogram.event)).options(
                selectinload(rel(AimbatEvent.parameters)),
                selectinload(rel(AimbatEvent.seismograms)).selectinload(
                    rel(AimbatSeismogram.parameters)
                ),
            ),
        )
    ).all()
    found = {seismogram.id for seismogram in seismograms}
    missing = [i for i in ids if i not in found]
    if missing:
        raise NoResultFound(
            "No AimbatSeismogram found with ID(s): " + ", ".join(map(str, missing))
        )

    seismograms = [s for s in seismograms if updates[s.id]]
    if not seismograms:
        return

    validated = [
        (
            seismogram,
            AimbatSeismogramParametersBase.model_validate(
                seismogram.parameters, update=dict(updates[seismogram.id])
            ),
        )
        for seismogram in seismograms
    ]
    for seismogram, parameters in validated:
        for name in updates[seismogram.id]:
            setattr(seismogram.parameters, name, getattr(parameters, name))
        session.add(seismogram)

    events = {seismogram.event.id: seismogram.event for seismogram in seismograms}
    for event in events.values():
        resync_quality(session, event)


def get_selected_seismograms(
    session: Session, event_id: UUID | None = None, all_events: bool = False
) -> Sequence[AimbatSeismogram]:
    """Get the selected seismograms for the given event.

    A selected seismogram is one whose `select` parameter is set, i.e. one
    that is included in the ICCS stack and, by default, in MCCC.

    Args:
        session: Database session.
        event_id: Event ID to get seismograms for (only used when all_events is False).
        all_events: Get the selected seismograms for all events.

    Returns:
        Selected seismograms.

    Raises:
        ValueError: If `all_events` is False and `event_id` is not given.
    """

    if all_events is True:
        logger.debug("Selecting seismograms for all events.")
        statement = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameters)
            .where(col(AimbatSeismogramParameters.select).is_(True))
        )
    else:
        if event_id is None:
            raise ValueError("An event must be provided when all_events is False.")
        logger.debug(f"Selecting seismograms for event {event_id} only.")
        statement = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameters)
            .where(col(AimbatSeismogramParameters.select).is_(True))
            .where(AimbatSeismogram.event_id == event_id)
        )

    statement = statement.options(
        selectinload(rel(AimbatSeismogram.station)),
        selectinload(rel(AimbatSeismogram.event)),
        selectinload(rel(AimbatSeismogram.parameters)),
        selectinload(rel(AimbatSeismogram.quality)),
    )
    seismograms = session.exec(statement).all()

    logger.debug(f"Found {len(seismograms)} selected seismograms.")

    return seismograms


def dump_seismogram_parameter_table(
    session: Session,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Dump the seismogram parameter table data to json serialisable list of dicts.

    Args:
        session: Database session.
        by_alias: Whether to use serialisation aliases for the field names in the output.
        by_title: Whether to use titles for the field names in the output.
        exclude: Set of field names to exclude from the output.
        event_id: Event ID to filter seismogram parameters by (if none is provided,
            all seismogram parameters for all events are dumped).

    Returns:
        list of dicts representing the seismogram parameters.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """
    logger.debug("Dumping AimbatSeismogramParameters table to json.")

    check_field_name_flags(by_alias, by_title)

    if event_id is not None:
        statement = (
            select(AimbatSeismogramParameters)
            .join(AimbatSeismogram)
            .where(AimbatSeismogram.event_id == event_id)
        )
    else:
        statement = select(AimbatSeismogramParameters)

    parameters = session.exec(statement).all()

    return dump_models(
        parameters,
        AimbatSeismogramParameters,
        by_alias=by_alias,
        by_title=by_title,
        exclude=exclude,
    )
