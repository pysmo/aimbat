"""Helpers for building and reading project state.

Functions that write take a session and flush. The caller commits.
"""

import uuid
from collections.abc import Iterable
from typing import Any

from pandas import Timedelta
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from pysmo import Station

from aimbat.core import default_phase_parameters, promote_picks, store_picks
from aimbat.io import DataType, SourcePick
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPick,
    AimbatSeismogram,
    AimbatSnapshot,
)

__all__ = ["add_empty_phase", "add_phase_from_picks", "phase_state", "station_key"]


def add_empty_phase(session: Session, event: AimbatEvent, name: str) -> AimbatPhase:
    """Add a phase with default parameters and no seismograms to `event`."""
    phase = AimbatPhase(name=name, parameters=default_phase_parameters(name))
    event.phases.append(phase)
    session.flush()
    return phase


def add_phase_from_picks(
    session: Session,
    seismograms: Iterable[AimbatSeismogram],
    name: str,
    *,
    offset: Timedelta = Timedelta(seconds=1),
) -> list[AimbatPick]:
    """Store and promote a pick named `name` for each seismogram.

    Each pick lies `offset` after the seismogram's first initial pick and is
    stored from its own SAC source in header `t9`. Promotion creates the
    phase if the event has none of that name.

    Returns:
        The stored picks.
    """
    picks: list[AimbatPick] = []
    for seismogram in seismograms:
        picks += store_picks(
            session,
            [
                SourcePick(
                    seismogram.phase_rows[0].initial_pick + offset, "t9", label=name
                )
            ],
            source_name=f"{name}-{seismogram.id}",
            source_type=DataType.SAC,
            source_seismogram=seismogram,
        ).stored
    promote_picks(session, picks)
    return picks


def phase_state(engine: Engine, phase_id: uuid.UUID) -> dict[str, Any]:
    """Return everything stored for a phase: parameters, rows, quality, snapshots.

    Rows are ordered by ID, so two states of one phase compare equal when
    nothing has changed.
    """
    with Session(engine) as session:
        phase = session.get_one(AimbatPhase, phase_id)
        rows = sorted(phase.seismogram_parameters, key=lambda r: str(r.id))
        return {
            "parameters": phase.parameters.model_dump(),
            "quality": None if phase.quality is None else phase.quality.model_dump(),
            "rows": [row.model_dump() for row in rows],
            "row_quality": [
                None if row.quality is None else row.quality.model_dump()
                for row in rows
            ],
            "snapshots": sorted(
                str(s)
                for s in session.exec(
                    select(AimbatSnapshot.id).where(
                        col(AimbatSnapshot.phase_id) == phase_id
                    )
                ).all()
            ),
        }


def station_key(station: Station) -> str:
    """Return `NETWORK.STATION` for a station."""
    return f"{station.network}.{station.name}"
