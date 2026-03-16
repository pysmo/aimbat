from collections.abc import Sequence
from typing import Any, Literal, overload
from uuid import UUID

from pandas import Timestamp
from pydantic import TypeAdapter
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat._types import SeismogramParameter
from aimbat.logger import logger
from aimbat.models import (
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersBase,
    AimbatSeismogramRead,
)
from aimbat.utils import get_title_map

__all__ = [
    "delete_seismogram",
    "set_seismogram_parameter",
    "reset_seismogram_parameters",
    "get_selected_seismograms",
    "dump_seismogram_table",
    "dump_seismogram_parameter_table",
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

    """

    logger.info(f"Deleting seismogram {seismogram_id}.")

    seismogram = session.get(AimbatSeismogram, seismogram_id)
    if seismogram is None:
        raise NoResultFound(f"No AimbatSeismogram found with {seismogram_id=}")

    session.delete(seismogram)
    session.commit()


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
        by_alias: Whether to use serialization aliases for the field names in the output.
        by_title: Whether to use titles for the field names in the output (only
            applicable when from_read_model is True). Mutually exclusive with by_alias.
        exclude: Set of field names to exclude from the output.
        event_id: Event ID to filter seismograms by (if none is provided,
            seismograms for all events are dumped).

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
        ValueError: If `by_title` is True but `from_read_model` is False.
    """
    logger.debug("Dumping AIMBAT seismogram table to json.")

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    if not from_read_model and by_title:
        raise ValueError("'by_title' is only supported when 'from_read_model' is True.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    if event_id is not None:
        statement = select(AimbatSeismogram).where(
            AimbatSeismogram.event_id == event_id
        )
    else:
        statement = select(AimbatSeismogram)

    seismograms = session.exec(statement).all()

    if from_read_model:
        seismogram_reads = [
            AimbatSeismogramRead.from_seismogram(s, session=session)
            for s in seismograms
        ]
        adapter_reads: TypeAdapter[Sequence[AimbatSeismogramRead]] = TypeAdapter(
            Sequence[AimbatSeismogramRead]
        )
        data = adapter_reads.dump_python(
            seismogram_reads, mode="json", exclude=exclude, by_alias=by_alias
        )

        if by_title:
            title_map = get_title_map(AimbatSeismogramRead)
            return [{title_map.get(k, k): v for k, v in row.items()} for row in data]

        return data

    adapter: TypeAdapter[Sequence[AimbatSeismogram]] = TypeAdapter(
        Sequence[AimbatSeismogram]
    )

    return adapter.dump_python(
        seismograms, mode="json", exclude=exclude, by_alias=by_alias
    )


def reset_seismogram_parameters(session: Session, seismogram_id: UUID) -> None:
    """Reset an AimbatSeismogram's parameters to their default values.

    All fields defined on AimbatSeismogramParametersBase are reset to the
    values produced by a fresh default instance, so newly added fields are
    picked up automatically.

    Args:
        session: Database session.
        seismogram_id: ID of seismogram to reset parameters for.
    """

    logger.info(f"Resetting parameters for seismogram {seismogram_id}.")

    seismogram = session.get(AimbatSeismogram, seismogram_id)
    if seismogram is None:
        raise NoResultFound(f"No AimbatSeismogram found with {seismogram_id=}")

    from ._iccs import clear_mccc_quality
    from ._snapshot import compute_parameters_hash, sync_from_matching_hash

    defaults = AimbatSeismogramParametersBase()
    for field_name in AimbatSeismogramParametersBase.model_fields:
        setattr(seismogram.parameters, field_name, getattr(defaults, field_name))
    session.add(seismogram)
    parameters_hash = compute_parameters_hash(seismogram.event)
    if not sync_from_matching_hash(session, parameters_hash):
        clear_mccc_quality(session, seismogram.event)


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

    """
    from ._iccs import clear_mccc_quality
    from ._snapshot import compute_parameters_hash, sync_from_matching_hash

    logger.debug(
        f"Setting seismogram {name=} to {value=} in seismogram {seismogram_id=}."
    )

    seismogram = session.get(AimbatSeismogram, seismogram_id)
    if seismogram is None:
        raise ValueError(f"No AimbatSeismogram found with {seismogram_id=}")

    parameters = AimbatSeismogramParametersBase.model_validate(
        seismogram.parameters, update={name: value}
    )
    setattr(seismogram.parameters, name, getattr(parameters, name))
    session.add(seismogram)
    parameters_hash = compute_parameters_hash(seismogram.event)
    if not sync_from_matching_hash(session, parameters_hash):
        clear_mccc_quality(session, seismogram.event)


def get_selected_seismograms(
    session: Session, event_id: UUID | None = None, all_events: bool = False
) -> Sequence[AimbatSeismogram]:
    """Get the selected seismograms for the given event.

    Args:
        session: Database session.
        event_id: Event ID to get seismograms for (only used when all_events is False).
        all_events: Get the selected seismograms for all events.

    Returns: Selected seismograms.
    """

    if all_events is True:
        logger.debug("Selecting seismograms for all events.")
        statement = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameters)
            .where(AimbatSeismogramParameters.select == 1)
        )
    else:
        if event_id is None:
            raise ValueError("An event must be provided when all_events is False.")
        logger.debug(f"Selecting seismograms for event {event_id} only.")
        statement = (
            select(AimbatSeismogram)
            .join(AimbatSeismogramParameters)
            .where(AimbatSeismogramParameters.select == 1)
            .where(AimbatSeismogram.event_id == event_id)
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
        by_alias: Whether to use serialization aliases for the field names in the output.
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

    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    if exclude is not None:
        exclude: dict[str, set] = {"__all__": exclude}  # type: ignore[no-redef]

    adapter: TypeAdapter[Sequence[AimbatSeismogramParameters]] = TypeAdapter(
        Sequence[AimbatSeismogramParameters]
    )

    if event_id is not None:
        statement = (
            select(AimbatSeismogramParameters)
            .join(AimbatSeismogram)
            .where(AimbatSeismogram.event_id == event_id)
        )
    else:
        statement = select(AimbatSeismogramParameters)

    parameters = session.exec(statement).all()

    data = adapter.dump_python(
        parameters, mode="json", exclude=exclude, by_alias=by_alias
    )

    if by_title:
        title_map = get_title_map(AimbatSeismogramParameters)
        return [{title_map.get(k, k): v for k, v in row.items()} for row in data]

    return data
