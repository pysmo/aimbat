"""This module defines the "Aimbat" classes.

These classes are ORMs that present data stored in a database
as classes to use with python in AIMBAT.
"""

from aimbat.config import settings
from aimbat.lib.typing import SeismogramFileType
from datetime import datetime, timedelta, timezone
from sqlmodel import Relationship, SQLModel, Field
from sqlalchemy.types import DateTime, TypeDecorator
import aimbat.lib.io as io
import numpy as np
import os
import uuid


class _DateTimeUTC(TypeDecorator):
    """Adds UTC tzinfo to datetime field in database when reading attributes."""

    impl = DateTime

    cache_ok = True

    def process_result_value(self, value, dialect):  # type: ignore
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc)
        return value


class AimbatFileCreate(SQLModel):
    """Class to store data file information."""

    filename: str | os.PathLike = Field(unique=True)
    filetype: SeismogramFileType = SeismogramFileType.SAC


class AimbatFile(SQLModel, table=True):
    """Class to store data file information."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    filename: str
    filetype: str
    seismogram_id: uuid.UUID = Field(
        default=None, foreign_key="aimbatseismogram.id", ondelete="CASCADE"
    )
    seismogram: "AimbatSeismogram" = Relationship(back_populates="file")


class AimbatEvent(SQLModel, table=True):
    """Store event information."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    "Unique ID."

    active: bool | None = Field(default=None, unique=True)
    "Indicates if an event is the active event."

    time: datetime = Field(unique=True, sa_type=_DateTimeUTC)
    "Event time."

    latitude: float
    "Event latitude."

    longitude: float
    "Event longitude."

    depth: float | None = None
    "Event depth."

    seismograms: list["AimbatSeismogram"] = Relationship(
        back_populates="event", cascade_delete=True
    )
    "List of seismograms of this event."

    parameters: "AimbatEventParameters" = Relationship(
        back_populates="event", cascade_delete=True
    )
    "Event parameters."

    snapshots: list["AimbatSnapshot"] = Relationship(
        back_populates="event", cascade_delete=True
    )
    "List of snapshots."


class AimbatEventParametersBase(SQLModel):
    """Base class that defines the event parameters used in AIMBAT.

    This class serves as a base that is inherited by the actual
    classes that create the database tables. The attributes in
    this class correspond exactl to the AIMBAT event parameters.
    """

    completed: bool = False
    "Mark an event as completed."

    min_ccnorm: float = Field(ge=0.0, le=1.0, default=settings.min_ccnorm)
    "Minimum cross-correlation used when automatically de-selecting seismograms."

    window_pre: timedelta = Field(lt=0, default=settings.window_pre)
    "Pre-pick window length."

    window_post: timedelta = Field(gt=0, default=settings.window_post)
    "Post-pick window length."


class AimbatEventParameters(AimbatEventParametersBase, table=True):
    """Processing parameters common to all seismograms of a particular event."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    "Unique ID."

    event_id: uuid.UUID = Field(
        default=None, foreign_key="aimbatevent.id", ondelete="CASCADE"
    )
    "Event ID these parameters are associated with."

    event: AimbatEvent = Relationship(back_populates="parameters")
    "Event these parameters are associated with."

    snapshots: list["AimbatEventParametersSnapshot"] = Relationship(
        back_populates="parameters", cascade_delete=True
    )
    "Snapshots these parameters are associated with."


class AimbatEventParametersSnapshot(AimbatEventParametersBase, table=True):
    """Event parameter snapshot."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    snapshot_id: uuid.UUID = Field(
        default=None, foreign_key="aimbatsnapshot.id", ondelete="CASCADE"
    )
    snapshot: "AimbatSnapshot" = Relationship(
        back_populates="event_parameters_snapshot"
    )
    parameters: AimbatEventParameters = Relationship(back_populates="snapshots")
    parameters_id: uuid.UUID = Field(
        default=None, foreign_key="aimbateventparameters.id", ondelete="CASCADE"
    )


class AimbatStation(SQLModel, table=True):
    """Class to store station information."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    "Unique ID."

    name: str = Field(allow_mutation=False)
    "Station name."

    latitude: float
    "Station latitude"

    longitude: float
    "Station longitude"

    network: str | None = Field(default=None, allow_mutation=False)
    "Network name."

    elevation: float | None = None
    "Station elevation."

    seismograms: list["AimbatSeismogram"] = Relationship(
        back_populates="station", cascade_delete=True
    )
    "Seismograms recorded at this station."


class AimbatSeismogram(SQLModel, table=True):
    """Class to store seismogram data"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    "Unique ID."

    begin_time: datetime = Field(sa_type=_DateTimeUTC)
    "Begin time of seismogram."

    delta: timedelta
    "Sampling interval."

    t0: datetime = Field(sa_type=_DateTimeUTC)
    "Initial pick."

    cached_length: int | None = None

    file: AimbatFile = Relationship(back_populates="seismogram", cascade_delete=True)
    station_id: uuid.UUID = Field(
        default=None, foreign_key="aimbatstation.id", ondelete="CASCADE"
    )
    station: AimbatStation = Relationship(back_populates="seismograms")
    event_id: uuid.UUID = Field(
        default=None, foreign_key="aimbatevent.id", ondelete="CASCADE"
    )
    event: AimbatEvent = Relationship(back_populates="seismograms")
    parameters: "AimbatSeismogramParameters" = Relationship(
        back_populates="seismogram",
        cascade_delete=True,
    )

    @property
    def flip(self) -> bool:
        return self.parameters.flip

    @flip.setter
    def flip(self, value: bool) -> None:
        self.parameters.flip = value

    @property
    def select(self) -> bool:
        return self.parameters.select

    @select.setter
    def select(self, value: bool) -> None:
        self.parameters.select = value

    @property
    def t1(self) -> datetime | None:
        return self.parameters.t1

    @t1.setter
    def t1(self, value: datetime | None) -> None:
        self.parameters.t1 = value

    def __len__(self) -> int:
        if self.cached_length is None:
            self.cached_length = np.size(self.data)
        return self.cached_length

    @property
    def end_time(self) -> datetime:
        if len(self) == 0:
            return self.begin_time
        return self.begin_time + self.delta * (len(self) - 1)

    @property
    def data(self) -> np.ndarray:
        if self.file is None:
            raise RuntimeError("I don't know which file to read data from")
        return io.read_seismogram_data_from_file(self.file.filename, self.file.filetype)

    @data.setter
    def data(self, value: np.ndarray) -> None:
        if self.file is None:
            raise RuntimeError("I don't know which file to write data to")
        io.write_seismogram_data_to_file(self.file.filename, self.file.filetype, value)
        self.cached_length = np.size(value)


class AimbatSeismogramParametersBase(SQLModel):
    """Base class that defines the seismogram parameters used in AIMBAT."""

    flip: bool = False
    "Whether or not the seismogram should be flipped."
    select: bool = True
    "Whether or not this seismogram should be used for processing."
    t1: datetime | None = Field(default=None, sa_type=_DateTimeUTC)
    """Working pick.

    This pick serves as working as well as output pick. It is changed by:

    1. Picking the phase arrival in the stack.
    2. Running ICCS.
    3. Running MCCC.
    """


class AimbatSeismogramParameters(AimbatSeismogramParametersBase, table=True):
    """Class to store ICCS processing parameters of a single seismogram."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    seismogram_id: uuid.UUID = Field(
        default=None, foreign_key="aimbatseismogram.id", ondelete="CASCADE"
    )
    seismogram: AimbatSeismogram = Relationship(back_populates="parameters")
    snapshots: list["AimbatSeismogramParametersSnapshot"] = Relationship(
        back_populates="parameters", cascade_delete=True
    )


class AimbatSeismogramParametersSnapshot(AimbatSeismogramParametersBase, table=True):
    """Class to store a snapshot of ICCS processing parameters of a single seismogram."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    seismogram_parameters_id: uuid.UUID = Field(
        foreign_key="aimbatseismogramparameters.id", ondelete="CASCADE"
    )
    parameters: AimbatSeismogramParameters = Relationship(back_populates="snapshots")
    snapshot_id: uuid.UUID = Field(
        default=None, foreign_key="aimbatsnapshot.id", ondelete="CASCADE"
    )
    snapshot: "AimbatSnapshot" = Relationship(
        back_populates="seismogram_parameters_snapshots"
    )


class AimbatSnapshot(SQLModel, table=True):
    """Class to store AIMBAT snapshots.

    The AimbatSnapshot class does not actually save any parameter data.
    It is used to keep track of the AimbatEventParametersSnapshot and
    AimbatSeismogramParametersSnapshot instances.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        unique=True,
        allow_mutation=False,
        sa_type=_DateTimeUTC,
    )
    comment: str | None = None
    event_parameters_snapshot: AimbatEventParametersSnapshot = Relationship(
        back_populates="snapshot", cascade_delete=True
    )
    seismogram_parameters_snapshots: list[AimbatSeismogramParametersSnapshot] = (
        Relationship(back_populates="snapshot", cascade_delete=True)
    )

    event_id: uuid.UUID = Field(
        default=None, foreign_key="aimbatevent.id", ondelete="CASCADE"
    )
    "Event ID this snapshot is associated with."

    event: AimbatEvent = Relationship(back_populates="snapshots")
    "Event this snapshot is associated with."


AimbatTypes = (
    AimbatFile
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
