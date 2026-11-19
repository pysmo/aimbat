"""One-line descriptions of records, for menus and lookups."""

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy import Select
    from sqlmodel import Session

    from aimbat.models import AimbatTypes

__all__ = ["describe_records"]

_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def describe_records(
    session: "Session",
    model_class: "type[AimbatTypes]",
    *,
    event_id: UUID | None = None,
    id_prefix: str | None = None,
) -> Iterator[tuple[UUID, str, str]]:
    """Yield each record's ID, short ID and a one-line description.

    Events are described by their time, stations as `NET.STA`, seismograms by
    station and event time, and snapshots by time and comment. Other records
    get an empty description.

    Args:
        session: Database session.
        model_class: The AIMBAT model whose records are described.
        event_id: Limit seismograms and snapshots to this event.
        id_prefix: Limit records to those whose ID starts with this, ignoring
            dashes.
    """
    from sqlmodel import col, select

    from aimbat.models import (
        AimbatEvent,
        AimbatPhase,
        AimbatSeismogram,
        AimbatSnapshot,
        AimbatStation,
    )
    from aimbat.utils import id_prefix_filter, uuid_shortener

    def short(record: Any) -> str:
        return uuid_shortener(session, record)

    def matching[S: Select[*tuple[Any, ...]]](statement: S) -> S:
        if id_prefix is None:
            return statement
        return statement.where(id_prefix_filter(model_class, id_prefix))

    if model_class is AimbatEvent:
        events = matching(select(AimbatEvent).order_by(col(AimbatEvent.time)))
        for event in session.exec(events):
            yield event.id, short(event), f"{event.time:{_TIME_FORMAT}}"
    elif model_class is AimbatStation:
        stations = matching(
            select(AimbatStation).order_by(
                col(AimbatStation.network), col(AimbatStation.name)
            )
        )
        for station in session.exec(stations):
            yield station.id, short(station), f"{station.network}.{station.name}"
    elif model_class is AimbatSeismogram:
        seismograms = matching(
            select(AimbatSeismogram, AimbatStation, AimbatEvent)
            .join(AimbatStation)
            .join(AimbatEvent)
            .order_by(col(AimbatStation.network), col(AimbatStation.name))
        )
        if event_id is not None:
            seismograms = seismograms.where(AimbatSeismogram.event_id == event_id)
        for seismogram, station, event in session.exec(seismograms):
            meta = f"{station.network}.{station.name} {event.time:{_TIME_FORMAT}}"
            yield seismogram.id, short(seismogram), meta
    elif model_class is AimbatSnapshot:
        snapshots = matching(select(AimbatSnapshot).order_by(col(AimbatSnapshot.time)))
        if event_id is not None:
            snapshots = snapshots.join(AimbatPhase).where(
                col(AimbatPhase.event_id) == event_id
            )
        for snapshot in session.exec(snapshots):
            meta = f"{snapshot.time:{_TIME_FORMAT}} {snapshot.comment or ''}"
            yield snapshot.id, short(snapshot), meta.strip()
    else:
        records: Any = session.exec(matching(select(model_class)))
        for record in records:
            yield record.id, short(record), ""
