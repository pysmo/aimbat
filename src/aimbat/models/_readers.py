import uuid
from sqlmodel import SQLModel
from typing import Self, TYPE_CHECKING
from aimbat._types import PydanticTimestamp

if TYPE_CHECKING:
    from ._models import AimbatEvent, AimbatSnapshot

__all__ = ["_AimbatEventRead", "_AimbatSnapshotRead"]


class _AimbatEventRead(SQLModel):
    """Read model for AimbatEvent including computed counts."""

    id: uuid.UUID
    active: bool | None
    time: PydanticTimestamp
    latitude: float
    longitude: float
    depth: float | None
    completed: bool = False
    seismogram_count: int
    station_count: int

    @classmethod
    def from_event(cls, event: "AimbatEvent") -> Self:
        """Create an AimbatEventRead from an AimbatEvent ORM instance."""
        return cls(
            id=event.id,
            active=event.active,
            time=event.time,
            latitude=event.latitude,
            longitude=event.longitude,
            depth=event.depth,
            completed=event.parameters.completed,
            seismogram_count=event.seismogram_count,
            station_count=event.station_count,
        )


class _AimbatSnapshotRead(SQLModel):
    """Read model for AimbatSnapshot with a seismogram count."""

    id: uuid.UUID
    date: PydanticTimestamp
    comment: str | None
    event_id: uuid.UUID
    seismogram_count: int
    selected_seismogram_count: int
    flipped_seismogram_count: int

    @classmethod
    def from_snapshot(cls, snapshot: "AimbatSnapshot") -> Self:
        """Create an AimbatSnapshotRead from an AimbatSnapshot ORM instance."""
        return cls(
            id=snapshot.id,
            date=snapshot.date,
            comment=snapshot.comment,
            event_id=snapshot.event_id,
            seismogram_count=snapshot.seismogram_count,
            selected_seismogram_count=snapshot.selected_seismogram_count,
            flipped_seismogram_count=snapshot.flipped_seismogram_count,
        )
