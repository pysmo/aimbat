"""ORM classes representing AIMBAT data stored in the database."""

import numpy as np
import numpy.typing as npt
import os
import uuid
from aimbat.io import DataType, read_seismogram_data, write_seismogram_data
from aimbat._types import (
    PydanticTimestamp,
    PydanticPositiveTimedelta,
    SAPandasTimestamp,
    SAPandasTimedelta,
)
from ._parameters import AimbatEventParametersBase, AimbatSeismogramParametersBase
from datetime import timezone
from sqlmodel import Relationship, SQLModel, Field, col, select
from sqlalchemy import func
from sqlalchemy.orm import column_property
from pydantic import computed_field
from typing import Self, TYPE_CHECKING
from pandas import Timestamp

__all__ = [
    "AimbatTypes",
    "AimbatDataSource",
    "AimbatStation",
    "AimbatEvent",
    "AimbatEventParameters",
    "AimbatEventParametersSnapshot",
    "AimbatSeismogram",
    "AimbatSeismogramParameters",
    "AimbatSeismogramParametersSnapshot",
    "AimbatSnapshot",
]


class _AimbatDataSourceCreate(SQLModel):
    """Input model for creating a new data source entry."""

    sourcename: str | os.PathLike = Field(
        unique=True, description="Path or name of the data source."
    )
    datatype: DataType = Field(
        default=DataType.SAC, description="Data type of the data source."
    )


class AimbatDataSource(SQLModel, table=True):
    """Class to store data source information."""

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    sourcename: str = Field(description="Path or name of the data source.")
    datatype: DataType = Field(description="Data type of the data source.")
    seismogram_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatseismogram.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent seismogram.",
    )
    seismogram: "AimbatSeismogram" = Relationship(back_populates="datasource")
    "The seismogram this data source belongs to."


class AimbatSeismogramParameters(AimbatSeismogramParametersBase, table=True):
    """Processing parameters for a single seismogram."""

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    seismogram_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatseismogram.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent seismogram.",
    )
    seismogram: "AimbatSeismogram" = Relationship(back_populates="parameters")
    "The seismogram these parameters belong to."
    snapshots: list["AimbatSeismogramParametersSnapshot"] = Relationship(
        back_populates="parameters", cascade_delete=True
    )
    "Parameter snapshots for this seismogram."


class AimbatSeismogramParametersSnapshot(AimbatSeismogramParametersBase, table=True):
    """Snapshot of processing parameters for a single seismogram."""

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    seismogram_parameters_id: uuid.UUID = Field(
        foreign_key="aimbatseismogramparameters.id",
        ondelete="CASCADE",
        description="Foreign key referencing the source seismogram parameters.",
    )
    parameters: AimbatSeismogramParameters = Relationship(back_populates="snapshots")
    "The seismogram parameters this snapshot was taken from."
    snapshot_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatsnapshot.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent snapshot.",
    )
    snapshot: "AimbatSnapshot" = Relationship(
        back_populates="seismogram_parameters_snapshots"
    )
    "The snapshot this record belongs to."


class AimbatEventParameters(AimbatEventParametersBase, table=True):
    """Processing parameters common to all seismograms of a particular event."""

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    event_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatevent.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent event.",
    )
    event: "AimbatEvent" = Relationship(back_populates="parameters")
    "The event these parameters belong to."
    snapshots: list["AimbatEventParametersSnapshot"] = Relationship(
        back_populates="parameters", cascade_delete=True
    )
    "Parameter snapshots for this event."


class AimbatEventParametersSnapshot(AimbatEventParametersBase, table=True):
    """Snapshot of processing parameters for a particular event."""

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    snapshot_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatsnapshot.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent snapshot.",
    )
    snapshot: "AimbatSnapshot" = Relationship(
        back_populates="event_parameters_snapshot"
    )
    "The snapshot this record belongs to."
    parameters: AimbatEventParameters = Relationship(back_populates="snapshots")
    "The event parameters this snapshot was taken from."
    parameters_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbateventparameters.id",
        ondelete="CASCADE",
        description="Foreign key referencing the source event parameters.",
    )


class AimbatSnapshot(SQLModel, table=True):
    """Container for a point-in-time snapshot of event and seismogram parameters.

    The AimbatSnapshot class does not actually save any parameter data.
    It is used to keep track of the AimbatEventParametersSnapshot and
    AimbatSeismogramParametersSnapshot instances.
    """

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    date: PydanticTimestamp = Field(
        default_factory=lambda: Timestamp.now(tz=timezone.utc),
        unique=True,
        allow_mutation=False,
        sa_type=SAPandasTimestamp,
        description="Timestamp when the snapshot was created.",
    )
    comment: str | None = Field(
        default=None, description="Optional comment for the snapshot."
    )
    event_parameters_snapshot: AimbatEventParametersSnapshot = Relationship(
        back_populates="snapshot", cascade_delete=True
    )
    "Event parameter snapshot associated with this snapshot."
    seismogram_parameters_snapshots: list[AimbatSeismogramParametersSnapshot] = (
        Relationship(back_populates="snapshot", cascade_delete=True)
    )
    "Seismogram parameter snapshots associated with this snapshot."
    event_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatevent.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent event.",
    )
    event: "AimbatEvent" = Relationship(back_populates="snapshots")
    "The event this snapshot belongs to."


class AimbatSeismogram(SQLModel, table=True):
    """Class to store seismogram metadata."""

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    begin_time: PydanticTimestamp = Field(
        sa_type=SAPandasTimestamp, description="Start time of the seismogram."
    )
    delta: PydanticPositiveTimedelta = Field(
        sa_type=SAPandasTimedelta, description="Sampling interval."
    )
    t0: PydanticTimestamp = Field(
        sa_type=SAPandasTimestamp, description="Initial phase arrival pick."
    )
    datasource: AimbatDataSource = Relationship(
        back_populates="seismogram", cascade_delete=True
    )
    "Data source for the seismogram waveform."
    station_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatstation.id",
        ondelete="CASCADE",
        description="Foreign key referencing the recording station.",
    )
    station: "AimbatStation" = Relationship(back_populates="seismograms")
    "The station that recorded this seismogram."
    event_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatevent.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent event.",
    )
    event: "AimbatEvent" = Relationship(back_populates="seismograms")
    "The event this seismogram belongs to."
    parameters: "AimbatSeismogramParameters" = Relationship(
        back_populates="seismogram",
        cascade_delete=True,
    )
    "Processing parameters for this seismogram."

    if TYPE_CHECKING:
        # Add same default values for type checking purposes
        # as in AimbatSeismogramParametersBase
        flip: bool = False
        select: bool = True
        t1: Timestamp | None = None
        data: npt.NDArray[np.float64] = np.array([])

        @property
        def end_time(self) -> Timestamp: ...

    else:

        @computed_field
        def end_time(self) -> PydanticTimestamp:
            """End time of the seismogram, derived from begin_time, delta, and data length."""
            if len(self.data) == 0:
                return self.begin_time
            return self.begin_time + self.delta * (len(self.data) - 1)

        @property
        def flip(self) -> bool:
            """Whether the seismogram should be flipped."""
            return self.parameters.flip

        @flip.setter
        def flip(self, value: bool) -> None:
            self.parameters.flip = value

        @property
        def select(self) -> bool:
            """Whether this seismogram should be used for processing."""
            return self.parameters.select

        @select.setter
        def select(self, value: bool) -> None:
            self.parameters.select = value

        @property
        def t1(self) -> Timestamp | None:
            """Working phase arrival pick."""
            return self.parameters.t1

        @t1.setter
        def t1(self, value: Timestamp | None) -> None:
            self.parameters.t1 = value

        @property
        def data(self) -> npt.NDArray[np.float64]:
            """Seismogram waveform data array."""
            if self.datasource is None:
                raise ValueError("Expected a valid datasource name, got None.")
            return read_seismogram_data(
                self.datasource.sourcename, self.datasource.datatype
            )

        @data.setter
        def data(self, value: npt.NDArray[np.float64]) -> None:
            if self.datasource is None:
                raise ValueError("Expected a valid datasource name, got None.")
            write_seismogram_data(
                self.datasource.sourcename, self.datasource.datatype, value
            )


class AimbatStation(SQLModel, table=True):
    """Class to store station information."""

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    name: str = Field(allow_mutation=False, description="Station name.")
    network: str = Field(allow_mutation=False, description="Network name.")
    location: str = Field(allow_mutation=False, description="Location ID.")
    channel: str = Field(allow_mutation=False, description="Channel code.")
    latitude: float = Field(description="Station latitude.")
    longitude: float = Field(description="Station longitude.")
    elevation: float | None = Field(default=None, description="Station elevation.")
    seismograms: list[AimbatSeismogram] = Relationship(
        back_populates="station", cascade_delete=True
    )
    "Seismograms recorded at this station."


class AimbatEvent(SQLModel, table=True):
    """Class to store seismic event information."""

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )

    active: bool | None = Field(
        default=None,
        unique=True,
        description="Indicates if an event is the active event.",
    )

    time: PydanticTimestamp = Field(
        unique=True,
        sa_type=SAPandasTimestamp,
        allow_mutation=False,
        description="Event time.",
    )

    latitude: float = Field(description="Event latitude.")
    longitude: float = Field(description="Event longitude.")
    depth: float | None = Field(default=None, description="Event depth.")
    seismograms: list[AimbatSeismogram] = Relationship(
        back_populates="event", cascade_delete=True
    )
    "List of seismograms of this event."

    parameters: AimbatEventParameters = Relationship(
        back_populates="event", cascade_delete=True
    )
    "Event parameters."

    snapshots: list[AimbatSnapshot] = Relationship(
        back_populates="event", cascade_delete=True
    )
    "List of snapshots."

    if TYPE_CHECKING:
        seismogram_count: int = 0
        station_count: int = 0


AimbatEvent.seismogram_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSeismogram.id)))
    .where(col(AimbatSeismogram.event_id) == col(AimbatEvent.id))
    .correlate_except(AimbatSeismogram)
    .scalar_subquery()
)
"Number of seismograms for this event."

AimbatEvent.station_count = column_property(  # type: ignore[assignment]
    select(func.count(func.distinct(col(AimbatSeismogram.station_id))))
    .where(col(AimbatSeismogram.event_id) == col(AimbatEvent.id))
    .correlate_except(AimbatSeismogram)
    .scalar_subquery()
)
"Number of unique stations for this event."


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
    def from_event(cls, event: AimbatEvent) -> Self:
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

    @classmethod
    def from_snapshot(cls, snapshot: AimbatSnapshot) -> Self:
        """Create an AimbatSnapshotRead from an AimbatSnapshot ORM instance."""
        return cls(
            id=snapshot.id,
            date=snapshot.date,
            comment=snapshot.comment,
            event_id=snapshot.event_id,
            seismogram_count=len(snapshot.seismogram_parameters_snapshots),
        )


type AimbatTypes = (
    AimbatDataSource
    | AimbatStation
    | AimbatEvent
    | AimbatEventParameters
    | AimbatSeismogram
    | AimbatSeismogramParameters
    | AimbatSnapshot
    | AimbatEventParametersSnapshot
    | AimbatSeismogramParametersSnapshot
)
"""Union of all AIMBAT models that exist in the database."""
