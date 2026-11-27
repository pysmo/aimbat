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
    AimbatPhase,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersBase,
    AimbatSeismogramRead,
)
from aimbat.types import SeismogramParameter
from aimbat.utils import check_field_name_flags, dump_models, rel

from ._phase import _with_phase_names
from ._session import flush_deletes
from ._validity import Validity

__all__ = [
    "delete_seismogram",
    "dump_seismogram_parameter_table",
    "dump_seismogram_table",
    "get_seismogram_parameters",
    "get_selected_rows",
    "reset_seismogram_parameters",
    "set_refined_picks",
    "set_seismogram_parameter",
    "set_seismogram_parameters",
]

type SeismogramParameterBool = Literal[
    SeismogramParameter.SELECT, SeismogramParameter.FLIP
]
type SeismogramParameterTimestamp = Literal[SeismogramParameter.REFINED_PICK]


def _row_loads() -> tuple[Any, ...]:
    """Loader options for a seismogram's rows with their phase, quality and pick."""
    rows = selectinload(rel(AimbatSeismogram.phase_rows))
    return (
        rows.selectinload(rel(AimbatSeismogramParameters.phase)),
        rows.selectinload(rel(AimbatSeismogramParameters.quality)),
        rows.selectinload(rel(AimbatSeismogramParameters.pick)),
    )


def _row(seismogram: AimbatSeismogram, phase_id: UUID) -> AimbatSeismogramParameters:
    """The row of a seismogram for a phase.

    Raises:
        NoResultFound: If the seismogram has no row for the phase.
    """
    for row in seismogram.phase_rows:
        if row.phase_id == phase_id:
            return row
    raise NoResultFound(f"Seismogram {seismogram.id} is not in phase {phase_id}.")


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


def get_seismogram_parameters(
    session: Session, phase_id: UUID, seismogram_id: UUID
) -> AimbatSeismogramParameters:
    """Return the processing state of a seismogram for a phase.

    Args:
        session: Database session.
        phase_id: ID of the phase.
        seismogram_id: Seismogram ID.

    Raises:
        NoResultFound: If no seismogram with the given ID is found, or it is
            not in the phase.
    """
    seismogram = session.get(AimbatSeismogram, seismogram_id)
    if seismogram is None:
        raise NoResultFound(f"No AimbatSeismogram found with {seismogram_id=}")
    return _row(seismogram, phase_id)


def dump_seismogram_table(
    session: Session,
    from_read_model: bool = False,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
    phase_name: str | None = None,
    phase_id: UUID | None = None,
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
        phase_name: Phase whose seismograms are dumped, with that phase's
            processing state in the read model. Without it, every seismogram
            is dumped, showing its only row (see
            `AimbatSeismogramRead.from_seismogram`).
        phase_id: Phase whose seismograms are dumped, as for `phase_name`.

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

    if phase_name is not None or phase_id is not None:
        statement = statement.join(
            AimbatSeismogramParameters,
            col(AimbatSeismogramParameters.seismogram_id) == col(AimbatSeismogram.id),
        ).join(
            AimbatPhase,
            col(AimbatPhase.id) == col(AimbatSeismogramParameters.phase_id),
        )
    if phase_name is not None:
        statement = statement.where(AimbatPhase.name == phase_name)
    if phase_id is not None:
        statement = statement.where(AimbatPhase.id == phase_id)

    statement = statement.options(
        selectinload(rel(AimbatSeismogram.station)),
        selectinload(rel(AimbatSeismogram.event)),
        *_row_loads(),
    )

    seismograms = session.exec(statement).all()

    if from_read_model:
        validity = Validity.read(session, event_id=event_id)
        seismogram_reads = [
            AimbatSeismogramRead.from_seismogram(
                s, validity, session=session, phase_name=phase_name, phase_id=phase_id
            )
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


def reset_seismogram_parameters(
    session: Session, phase_id: UUID, seismogram_id: UUID
) -> None:
    """Reset the parameters of a seismogram in a phase to their default values.

    All fields defined on AimbatSeismogramParametersBase are reset to the
    values produced by a fresh default instance, so newly added fields are
    picked up automatically. This includes `refined_pick`, so a manual pick
    is discarded along with `select` and `flip`.

    Args:
        session: Database session.
        phase_id: ID of the phase.
        seismogram_id: ID of seismogram to reset parameters for.

    Raises:
        NoResultFound: If no seismogram with the given ID is found, or it is
            not in the phase.
    """

    logger.info(
        f"Resetting parameters for seismogram {seismogram_id} in phase {phase_id}."
    )

    seismogram = session.get(AimbatSeismogram, seismogram_id)
    if seismogram is None:
        raise NoResultFound(f"No AimbatSeismogram found with {seismogram_id=}")

    from ._snapshot import resync_quality

    row = _row(seismogram, phase_id)
    defaults = AimbatSeismogramParametersBase()
    for field_name in AimbatSeismogramParametersBase.model_fields:
        setattr(row, field_name, getattr(defaults, field_name))
    session.add(row)
    resync_quality(session, phase_id)


@overload
def set_seismogram_parameter(
    session: Session,
    phase_id: UUID,
    seismogram_id: UUID,
    name: SeismogramParameterBool,
    value: bool | str,
) -> None: ...


@overload
def set_seismogram_parameter(
    session: Session,
    phase_id: UUID,
    seismogram_id: UUID,
    name: SeismogramParameterTimestamp,
    value: Timestamp,
) -> None: ...


@overload
def set_seismogram_parameter(
    session: Session,
    phase_id: UUID,
    seismogram_id: UUID,
    name: SeismogramParameter,
    value: Timestamp | bool | str,
) -> None: ...


def set_seismogram_parameter(
    session: Session,
    phase_id: UUID,
    seismogram_id: UUID,
    name: SeismogramParameter,
    value: Timestamp | bool | str,
) -> None:
    """Set a parameter of a seismogram in a phase.

    Args:
        session: Database session
        phase_id: ID of the phase.
        seismogram_id: Seismogram id.
        name: Name of the parameter.
        value: Value to set parameter to.

    Raises:
        NoResultFound: If no seismogram with the given ID is found, or it is
            not in the phase.
        ValidationError: If `value` fails Pydantic validation for `name`.
    """
    set_seismogram_parameters(session, phase_id, [seismogram_id], {name: value})


def set_seismogram_parameters(
    session: Session,
    phase_id: UUID,
    seismogram_ids: Sequence[UUID],
    values: Mapping[SeismogramParameter, Timestamp | bool | str],
) -> None:
    """Set the same parameter values on several seismograms of a phase at once.

    Every seismogram and value is checked before anything changes, so an
    unknown ID or an invalid value leaves all seismograms as they were.

    Args:
        session: Database session.
        phase_id: ID of the phase.
        seismogram_ids: IDs of the seismograms to update. Duplicates are
            ignored. An empty sequence is a no-op.
        values: New value for each parameter, keyed by parameter name. An
            empty mapping is a no-op.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram of the phase.
        ValidationError: If any value fails Pydantic validation.
    """
    updates = {str(name): value for name, value in values.items()}
    logger.debug(f"Setting {updates} for {len(seismogram_ids)} seismogram(s).")
    _update_seismograms(session, phase_id, dict.fromkeys(seismogram_ids, updates))


def set_refined_picks(
    session: Session, phase_id: UUID, picks: Mapping[UUID, Timestamp]
) -> None:
    """Set the refined pick of several seismograms of a phase, each to its own value.

    Every seismogram and pick is checked before anything changes, so an
    unknown ID or an invalid pick leaves all seismograms as they were.

    Args:
        session: Database session.
        phase_id: ID of the phase.
        picks: New refined pick for each seismogram, keyed by seismogram ID.
            An empty mapping is a no-op.

    Raises:
        NoResultFound: If any of the IDs is not a seismogram of the phase.
        ValidationError: If any pick fails Pydantic validation.
    """
    logger.debug(f"Setting refined picks for {len(picks)} seismogram(s).")
    _update_seismograms(
        session,
        phase_id,
        {
            seismogram_id: {str(SeismogramParameter.REFINED_PICK): pick}
            for seismogram_id, pick in picks.items()
        },
    )


def _update_seismograms(
    session: Session,
    phase_id: UUID,
    updates: Mapping[UUID, Mapping[str, Timestamp | bool | str]],
) -> None:
    """Apply per-seismogram parameter updates after validating all of them."""
    from ._snapshot import resync_quality

    ids = list(updates)

    seismograms = session.exec(
        select(AimbatSeismogram)
        .where(col(AimbatSeismogram.id).in_(ids))
        .options(selectinload(rel(AimbatSeismogram.phase_rows)))
    ).all()
    found = {
        seismogram.id
        for seismogram in seismograms
        if any(row.phase_id == phase_id for row in seismogram.phase_rows)
    }
    missing = [i for i in ids if i not in found]
    if missing:
        raise NoResultFound(
            f"No seismogram of phase {phase_id} found with ID(s): "
            + ", ".join(map(str, missing))
        )

    seismograms = [s for s in seismograms if updates[s.id]]
    if not seismograms:
        return

    rows = {seismogram.id: _row(seismogram, phase_id) for seismogram in seismograms}
    validated = [
        (
            seismogram,
            AimbatSeismogramParametersBase.model_validate(
                rows[seismogram.id], update=dict(updates[seismogram.id])
            ),
        )
        for seismogram in seismograms
    ]
    for seismogram, parameters in validated:
        row = rows[seismogram.id]
        for name in updates[seismogram.id]:
            setattr(row, name, getattr(parameters, name))
        session.add(row)

    resync_quality(session, phase_id)


def get_selected_rows(
    session: Session, phase_id: UUID
) -> Sequence[AimbatSeismogramParameters]:
    """Get the selected seismograms of a phase, as their rows for it.

    A selected seismogram is one whose `select` parameter is set for the
    phase, i.e. one that is included in the phase's ICCS stack and, by
    default, in MCCC.

    Args:
        session: Database session.
        phase_id: ID of the phase.

    Returns:
        The rows of the phase with `select` set.
    """
    logger.debug(f"Getting selected seismograms of phase {phase_id}.")

    rows = session.exec(
        select(AimbatSeismogramParameters)
        .where(col(AimbatSeismogramParameters.phase_id) == phase_id)
        .where(col(AimbatSeismogramParameters.select).is_(True))
        .options(
            selectinload(rel(AimbatSeismogramParameters.seismogram)),
            selectinload(rel(AimbatSeismogramParameters.quality)),
            selectinload(rel(AimbatSeismogramParameters.pick)),
        )
    ).all()

    logger.debug(f"Found {len(rows)} selected seismograms.")

    return rows


def dump_seismogram_parameter_table(
    session: Session,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
    event_id: UUID | None = None,
    phase_name: str | None = None,
) -> list[dict[str, Any]]:
    """Dump the seismogram parameter table data to json serialisable list of dicts.

    Each record carries the name and component of its phase next to the
    phase ID.

    Args:
        session: Database session.
        by_alias: Whether to use serialisation aliases for the field names in the output.
        by_title: Whether to use titles for the field names in the output.
        exclude: Set of field names to exclude from the output.
        event_id: Event ID to filter seismogram parameters by (if none is provided,
            all seismogram parameters for all events are dumped).
        phase_name: Only the rows of phases of this name, across the events
            covered.

    Returns:
        list of dicts representing the seismogram parameters.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """
    logger.debug("Dumping AimbatSeismogramParameters table to json.")

    check_field_name_flags(by_alias, by_title)

    statement = select(AimbatSeismogramParameters).join(AimbatPhase)
    if event_id is not None:
        statement = statement.where(col(AimbatPhase.event_id) == event_id)
    if phase_name is not None:
        statement = statement.where(col(AimbatPhase.name) == phase_name)
    statement = statement.options(selectinload(rel(AimbatSeismogramParameters.phase)))

    parameters = session.exec(statement).all()

    data = dump_models(
        parameters,
        AimbatSeismogramParameters,
        by_alias=by_alias,
        by_title=by_title,
        exclude=exclude,
    )
    return _with_phase_names(
        data,
        (row.phase for row in parameters),
        by_alias=by_alias,
        by_title=by_title,
    )
