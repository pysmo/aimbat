"""This module defines the "Aimbat" classes.

These classes are ORMs that present data stored in a database
as classes to use with python in AIMBAT.
"""

from aimbat.lib.types import SeismogramFileType, ProjectDefault
from aimbat.lib.io import read_seismogram_data_from_file, write_seismogram_data_to_file
from datetime import datetime, timedelta, timezone
from sqlmodel import Relationship, SQLModel, Field
import numpy as np


class AimbatDefault(SQLModel, table=True):
    """Class to store AIMBAT defaults."""

    id: int | None = Field(default=None, primary_key=True)
    aimbat: bool = Field(default=True, description="AIMBAT is awesome!")
    sampledata_dir: str = Field(
        default="./sample-data",
        description="Directory to store downloaded sample data.",
    )
    sampledata_src: str = Field(
        default="https://github.com/pysmo/data-example/archive/refs/heads/aimbat_v2.zip",
        description="URL where sample data is downloaded from.",
    )
    delta_tolerance: int = Field(
        default=9,
        description="Round delta to N decimals when checking for different sampling rates in SAC files.",
    )
    initial_pick_header: str = Field(
        default="t0", description="SAC header field where initial pick is stored."
    )
    initial_time_window_width: float = Field(
        default=15, description="Width of initial timewindow in seconds."
    )

    def reset(self, name: ProjectDefault) -> None:
        default = self.model_fields.get(name).default  # type: ignore
        setattr(self, name, default)

    def description(self, name: ProjectDefault) -> str:
        return self.model_fields.get(name).description  # type: ignore


class AimbatFileBase(SQLModel):
    """Class to store data file information."""

    filename: str = Field(unique=True)


class AimbatFileCreate(AimbatFileBase):
    """Class to store data file information."""

    filetype: SeismogramFileType = SeismogramFileType.SAC


class AimbatFile(AimbatFileBase, table=True):
    """Class to store data file information."""

    id: int | None = Field(default=None, primary_key=True)
    filetype: str
    seismogram: "AimbatSeismogram" = Relationship(
        back_populates="file", cascade_delete=True
    )


class EventStationLink(SQLModel, table=True):
    event_id: int | None = Field(
        default=None, foreign_key="aimbatevent.id", primary_key=True, ondelete="CASCADE"
    )
    station_id: int | None = Field(
        default=None,
        foreign_key="aimbatstation.id",
        primary_key=True,
        ondelete="CASCADE",
    )


class AimbatActiveEvent(SQLModel, table=True):
    """Stores the active event id."""

    id: int = Field(default=1, primary_key=True, const=True)
    event_id: int | None = Field(foreign_key="aimbatevent.id", ondelete="CASCADE")
    event: "AimbatEvent" = Relationship(back_populates="active_event")


class AimbatEvent(SQLModel, table=True):
    """Class to store event information."""

    id: int | None = Field(default=None, primary_key=True)
    time_db: datetime = Field(unique=True)
    latitude: float
    longitude: float
    depth: float | None = None
    stations: list["AimbatStation"] = Relationship(
        back_populates="events", link_model=EventStationLink
    )
    seismograms: list["AimbatSeismogram"] = Relationship(
        back_populates="event", cascade_delete=True
    )
    parameters: "AimbatEventParameters" = Relationship(
        back_populates="event", cascade_delete=True
    )
    active_event: AimbatActiveEvent = Relationship(
        back_populates="event", cascade_delete=True
    )

    @property
    def time(self) -> datetime:
        return self.time_db.replace(tzinfo=timezone.utc)

    @time.setter
    def time(self, value: datetime) -> None:
        self.time_db = value


class AimbatEventParametersBase(SQLModel):
    """Base class that defines the event parameters used in AIMBAT"""

    completed: bool = False
    window_pre: timedelta
    window_post: timedelta


class AimbatEventParameters(AimbatEventParametersBase, table=True):
    """Processing parameters common to all seismograms of a particular event."""

    id: int | None = Field(default=None, primary_key=True)
    event_id: int | None = Field(foreign_key="aimbatevent.id", ondelete="CASCADE")
    event: AimbatEvent = Relationship(back_populates="parameters")
    snapshots: list["AimbatEventParametersSnapshot"] = Relationship(
        back_populates="parameters", cascade_delete=True
    )


class AimbatEventParametersSnapshot(AimbatEventParametersBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int | None = Field(foreign_key="aimbatsnapshot.id", ondelete="CASCADE")
    snapshot: "AimbatSnapshot" = Relationship(
        back_populates="event_parameters_snapshot"
    )
    parameters: AimbatEventParameters = Relationship(back_populates="snapshots")
    parameters_id: int | None = Field(
        foreign_key="aimbateventparameters.id", ondelete="CASCADE"
    )


class AimbatStation(SQLModel, table=True):
    """Class to store station information."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(allow_mutation=False)
    latitude: float
    longitude: float
    network: str | None = Field(default=None, allow_mutation=False)
    elevation: float | None = None
    seismograms: list["AimbatSeismogram"] = Relationship(
        back_populates="station", cascade_delete=True
    )
    events: list[AimbatEvent] = Relationship(
        back_populates="stations", link_model=EventStationLink
    )


class AimbatSeismogram(SQLModel, table=True):
    """Class to store seismogram data"""

    id: int | None = Field(default=None, primary_key=True)

    begin_time_db: datetime = Field()
    delta: float
    t0: datetime
    cached_length: int | None = None

    file_id: int | None = Field(
        default=None, foreign_key="aimbatfile.id", ondelete="CASCADE"
    )
    file: AimbatFile = Relationship(back_populates="seismogram")
    station_id: int | None = Field(foreign_key="aimbatstation.id", ondelete="CASCADE")
    station: AimbatStation = Relationship(back_populates="seismograms")
    event_id: int | None = Field(foreign_key="aimbatevent.id", ondelete="CASCADE")
    event: AimbatEvent = Relationship(back_populates="seismograms")
    parameters: "AimbatSeismogramParameters" = Relationship(
        back_populates="seismogram",
        cascade_delete=True,
    )

    def __len__(self) -> int:
        if self.cached_length is None:
            self.cached_length = np.size(self.data)
        return self.cached_length

    @property
    def begin_time(self) -> datetime:
        return self.begin_time_db.replace(tzinfo=timezone.utc)

    @begin_time.setter
    def begin_time(self, value: datetime) -> None:
        self.begin_time_db = value

    @property
    def end_time(self) -> datetime:
        if len(self) == 0:
            return self.begin_time
        return self.begin_time + timedelta(seconds=self.delta * (len(self) - 1))

    @property
    def data(self) -> np.ndarray:
        if self.file_id is None:
            raise RuntimeError("I don't know which file to read data from")
        return read_seismogram_data_from_file(self.file.filename, self.file.filetype)

    @data.setter
    def data(self, value: np.ndarray) -> None:
        if self.file_id is None:
            raise RuntimeError("I don't know which file to write data to")
        write_seismogram_data_to_file(self.file.filename, self.file.filetype, value)
        self.cached_length = np.size(value)


class AimbatSeismogramParametersBase(SQLModel):
    """Base class that defines the seismogram parameters used in AIMBAT."""

    select: bool = True
    t1: datetime | None = None
    t2: datetime | None = None


class AimbatSeismogramParameters(AimbatSeismogramParametersBase, table=True):
    """Class to store ICCS processing parameters of a single seismogram."""

    id: int | None = Field(default=None, primary_key=True)
    seismogram_id: int | None = Field(
        foreign_key="aimbatseismogram.id", ondelete="CASCADE"
    )
    seismogram: AimbatSeismogram = Relationship(back_populates="parameters")
    snapshots: list["AimbatSeismogramParametersSnapshot"] = Relationship(
        back_populates="parameters", cascade_delete=True
    )


class AimbatSeismogramParametersSnapshot(AimbatSeismogramParametersBase, table=True):
    """Class to store a snapshot of ICCS processing parameters of a single seismogram."""

    id: int | None = Field(default=None, primary_key=True)
    seismogram_parameters_id: int | None = Field(
        foreign_key="aimbatseismogramparameters.id", ondelete="CASCADE"
    )
    parameters: AimbatSeismogramParameters = Relationship(back_populates="snapshots")
    snapshot_id: int | None = Field(foreign_key="aimbatsnapshot.id", ondelete="CASCADE")
    snapshot: "AimbatSnapshot" = Relationship(
        back_populates="seismogram_parameters_snapshots"
    )


class AimbatSnapshot(SQLModel, table=True):
    """Class to store AIMBAT snapshots.

    The AimbatSnapshot class does not actually save any parameter data.
    It is used to keep track of the AimbatEventParametersSnapshot and
    AimbatSeismogramParametersSnapshot instances.
    """

    id: int | None = Field(default=None, primary_key=True)
    date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        unique=True,
        allow_mutation=False,
    )
    comment: str | None = None
    event_parameters_snapshot: AimbatEventParametersSnapshot = Relationship(
        back_populates="snapshot", cascade_delete=True
    )
    seismogram_parameters_snapshots: list[AimbatSeismogramParametersSnapshot] = (
        Relationship(back_populates="snapshot", cascade_delete=True)
    )
