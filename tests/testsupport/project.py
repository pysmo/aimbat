"""Helpers for building and reading project state.

Functions that write take a session and flush. The caller commits. Functions
that take an engine open their own session, and commit if they write.
"""

import uuid
from collections.abc import Iterable
from typing import Any

import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, col, create_engine, select

from pysmo import Station

from aimbat import settings
from aimbat.core import default_phase_parameters, promote_picks, store_picks
from aimbat.core._validity import compute_digests, encode_members
from aimbat.io import DataType, SourcePick, StationEventTarget
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatPhase,
    AimbatPhaseQuality,
    AimbatPick,
    AimbatSeismogram,
    AimbatSeismogramQuality,
    AimbatSnapshot,
    AimbatStation,
)

__all__ = [
    "BEGIN",
    "ORIGIN",
    "add_empty_phase",
    "add_event",
    "add_phase_from_picks",
    "add_seismogram",
    "add_station",
    "add_unpromoted_pick",
    "at",
    "first",
    "phase_state",
    "set_event_tolerances",
    "stamp_quality",
    "station_key",
    "store_pick",
    "throwaway_session",
]

ORIGIN = Timestamp("2020-01-01T00:00:00", tz="UTC")
"""Origin time of events built with `add_event`."""

BEGIN = ORIGIN + Timedelta(minutes=5)
"""Begin time of seismograms built with `add_seismogram`."""


def at(seconds: float) -> Timestamp:
    """Return the time `seconds` after `BEGIN`."""
    return BEGIN + Timedelta(seconds=seconds)


def set_event_tolerances(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set non-strict event matching with 1 s and 60 s tolerances."""
    monkeypatch.setattr(settings, "event_duplicate_strict", False)
    monkeypatch.setattr(settings, "event_duplicate_tolerance", Timedelta(seconds=1))
    monkeypatch.setattr(
        settings, "event_duplicate_raise_tolerance", Timedelta(seconds=60)
    )


def add_event(session: Session, time: Timestamp = ORIGIN) -> AimbatEvent:
    """Add an event at `time`, latitude and longitude 0."""
    event = AimbatEvent(time=time, latitude=0.0, longitude=0.0)
    session.add(event)
    session.flush()
    return event


def throwaway_session() -> Session:
    """Return a session on an empty in-memory database without a project."""
    return Session(create_engine("sqlite://"))


def first[T: SQLModel](session: Session, model: type[T]) -> T:
    """Return the first row of `model`, failing the test if there is none."""
    row = session.exec(select(model)).first()
    assert row is not None, f"no {model.__name__} in the project"
    return row


def add_station(
    session: Session, *, name: str = "ABC", channel: str = "BHZ", location: str = "00"
) -> AimbatStation:
    """Add station `name` of network XX, or return the one stored."""
    existing = session.exec(
        select(AimbatStation)
        .where(AimbatStation.network == "XX")
        .where(AimbatStation.name == name)
        .where(AimbatStation.location == location)
        .where(AimbatStation.channel == channel)
    ).one_or_none()
    if existing is not None:
        return existing
    station = AimbatStation(
        name=name,
        network="XX",
        location=location,
        channel=channel,
        latitude=10.0,
        longitude=10.0,
    )
    session.add(station)
    session.flush()
    return station


def add_seismogram(
    session: Session,
    event: AimbatEvent,
    *,
    station: AimbatStation | None = None,
    name: str = "ABC",
    channel: str = "BHZ",
    location: str = "00",
    delta: float = 0.05,
) -> AimbatSeismogram:
    """Add a seismogram of `event` beginning at `BEGIN`, sampled every `delta` s.

    Without `station`, a new station is built from `name`, `channel` and
    `location`. The SAC data source gets a unique name.
    """
    if station is None:
        station = add_station(session, name=name, channel=channel, location=location)
    seismogram = AimbatSeismogram(
        begin_time=BEGIN,
        delta=Timedelta(seconds=delta),
        event=event,
        station=station,
    )
    seismogram.datasource = AimbatDataSource(
        sourcename=f"/data/{uuid.uuid4().hex}.sac", datatype=DataType.SAC
    )
    session.add(seismogram)
    session.flush()
    return seismogram


def store_pick(
    session: Session,
    seismogram: AimbatSeismogram | None,
    key: str,
    *,
    seconds: float = 30,
    label: str | None = "P",
    target: StationEventTarget | None = None,
    source: str = "/data/picks.json",
) -> AimbatPick:
    """Store one pick `seconds` after `BEGIN`, read from `source` under `key`."""
    (pick,) = store_picks(
        session,
        [SourcePick(at(seconds), key, label=label, target=target)],
        source_name=source,
        source_type=DataType.SAC,
        source_seismogram=seismogram,
    ).stored
    return pick


def add_empty_phase(
    session: Session, event: AimbatEvent, name: str, component: str = ""
) -> AimbatPhase:
    """Add a phase with default parameters and no seismograms to `event`."""
    phase = AimbatPhase(
        name=name,
        component=component,
        parameters=default_phase_parameters(name, component),
    )
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


def add_unpromoted_pick(engine: Engine, event_id: str, label: str | None) -> str:
    """Store a matched pick that is not promoted, on one seismogram of the event.

    The pick lies 5 s after the seismogram's first initial pick.

    Returns:
        The ID of the pick.
    """
    with Session(engine) as session:
        event = session.get_one(AimbatEvent, uuid.UUID(event_id))
        seismogram = sorted(event.seismograms, key=lambda s: str(s.id))[0]
        (pick,) = store_picks(
            session,
            [
                SourcePick(
                    seismogram.phase_rows[0].initial_pick + Timedelta(seconds=5),
                    "extra",
                    label=label,
                )
            ],
            source_name="extra.json",
            source_type=DataType.SAC,
            source_seismogram=seismogram,
        ).stored
        session.commit()
        return str(pick.id)


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


def stamp_quality(session: Session, event_id: uuid.UUID | None = None) -> None:
    """Stamp live quality as computed from the current parameters.

    Covers the phases of `event_id`, or every phase. The MCCC run's members
    are taken to be the rows with MCCC values.
    """
    for phase_id, digests in compute_digests(session, event_id=event_id).items():
        rows = session.exec(
            select(AimbatSeismogramQuality).where(
                col(AimbatSeismogramQuality.seismogram_parameters_id).in_(
                    list(digests.seismogram_cc)
                )
            )
        ).all()
        for row in rows:
            row.iccs_fingerprint = digests.seismogram_cc[row.seismogram_parameters_id]
        quality = session.exec(
            select(AimbatPhaseQuality).where(
                col(AimbatPhaseQuality.phase_id) == phase_id
            )
        ).first()
        if quality is not None:
            members = {
                r.seismogram_parameters_id for r in rows if r.mccc_cc_mean is not None
            }
            quality.mccc_members = encode_members(members)
            quality.mccc_fingerprint = digests.mccc(members)
    session.flush()


def station_key(station: Station) -> str:
    """Return `NETWORK.STATION` for a station."""
    return f"{station.network}.{station.name}"
