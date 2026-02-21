"""This module defines the "Aimbat" classes.

These classes are ORMs that present data stored in a database
as classes to use with python in AIMBAT.
"""

from ._sqlalchemy import SAPandasTimestamp, SAPandasTimedelta
from aimbat import settings
from aimbat._lib._mixins import EventParametersValidatorMixin
from aimbat.io import read_seismogram_data, write_seismogram_data
from aimbat.aimbat_types import (
    DataType,
    PydanticTimestamp,
    PydanticNegativeTimedelta,
    PydanticPositiveTimedelta,
)
from datetime import timezone
from sqlmodel import Relationship, SQLModel, Field
from pydantic import computed_field
from typing import TYPE_CHECKING
from pandas import Timestamp
import numpy as np
import os
import uuid

__all__ = [
    "AimbatTypes",
    "AimbatDataSource",
    "AimbatDataSourceCreate",
    "AimbatStation",
    "AimbatEvent",
    "AimbatEventParametersBase",
    "AimbatEventParameters",
    "AimbatEventParametersSnapshot",
    "AimbatSeismogram",
    "AimbatSeismogramParameters",
    "AimbatSeismogramParametersBase",
    "AimbatSeismogramParametersSnapshot",
    "AimbatSnapshot",
]


class AimbatDataSourceCreate(SQLModel):
    """Class to store data source information."""

    sourcename: str | os.PathLike = Field(unique=True)
    datatype: DataType = DataType.SAC


class AimbatDataSource(SQLModel, table=True):
    """Class to store data source information."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    sourcename: str
    datatype: DataType
    seismogram_id: uuid.UUID = Field(
        default=None, foreign_key="aimbatseismogram.id", ondelete="CASCADE"
    )
    seismogram: "AimbatSeismogram" = Relationship(back_populates="datasource")


class AimbatEvent(SQLModel, table=True):
    """Store event information."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    "Unique ID."

    active: bool | None = Field(default=None, unique=True)
    "Indicates if an event is the active event."

    time: PydanticTimestamp = Field(
        unique=True, sa_type=SAPandasTimestamp, allow_mutation=False
    )
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

    min_ccnorm: float = Field(
        ge=0.0, le=1.0, default_factory=lambda: settings.min_ccnorm
    )
    "Minimum cross-correlation used when automatically de-selecting seismograms."

    window_pre: PydanticNegativeTimedelta = Field(
        sa_type=SAPandasTimedelta, default_factory=lambda: settings.window_pre
    )
    "Pre-pick window length."

    window_post: PydanticPositiveTimedelta = Field(
        sa_type=SAPandasTimedelta, default_factory=lambda: settings.window_post
    )
    "Post-pick window length."

    bandpass_apply: bool = Field(default_factory=lambda: settings.bandpass_apply)
    "Whether to apply bandpass filter to seismograms."

    bandpass_fmin: float = Field(default_factory=lambda: settings.bandpass_fmin, ge=0)
    "Minimum frequency for bandpass filter (ignored if `bandpass_apply` is False)."

    bandpass_fmax: float = Field(default_factory=lambda: settings.bandpass_fmax, gt=0)
    "Maximum frequency for bandpass filter (ignored if `bandpass_apply` is False)."


class AimbatEventParameters(
    AimbatEventParametersBase, EventParametersValidatorMixin, table=True
):
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

    network: str = Field(allow_mutation=False)
    "Network name."

    location: str = Field(allow_mutation=False)
    "Location ID."

    channel: str = Field(allow_mutation=False)
    "Channel code."

    latitude: float
    "Station latitude"

    longitude: float
    "Station longitude"

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

    begin_time: PydanticTimestamp = Field(sa_type=SAPandasTimestamp)
    "Begin time of seismogram."

    delta: PydanticPositiveTimedelta = Field(sa_type=SAPandasTimedelta)
    "Sampling interval."

    t0: PydanticTimestamp = Field(sa_type=SAPandasTimestamp)
    "Initial pick."

    datasource: AimbatDataSource = Relationship(
        back_populates="seismogram", cascade_delete=True
    )
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

    def __len__(self) -> int:
        return np.size(self.data)

    if TYPE_CHECKING:
        flip: bool
        select: bool
        t1: Timestamp | None
        data: np.ndarray

        @property
        def end_time(self) -> Timestamp: ...

    else:

        @computed_field
        def end_time(self) -> PydanticTimestamp:
            if len(self) == 0:
                return self.begin_time
            return self.begin_time + self.delta * (len(self) - 1)

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
        def t1(self) -> Timestamp | None:
            return self.parameters.t1

        @t1.setter
        def t1(self, value: Timestamp | None) -> None:
            self.parameters.t1 = value

        @property
        def data(self) -> np.ndarray:
            if self.datasource is None:
                raise ValueError("Expected a valid datasource name, got None.")
            return read_seismogram_data(
                self.datasource.sourcename, self.datasource.datatype
            )

        @data.setter
        def data(self, value: np.ndarray) -> None:
            if self.datasource is None:
                raise ValueError("Expected a valid datasource name, got None.")
            write_seismogram_data(
                self.datasource.sourcename, self.datasource.datatype, value
            )


class AimbatSeismogramParametersBase(SQLModel):
    """Base class that defines the seismogram parameters used in AIMBAT."""

    flip: bool = False
    "Whether or not the seismogram should be flipped."

    select: bool = True
    "Whether or not this seismogram should be used for processing."

    t1: PydanticTimestamp | None = Field(default=None, sa_type=SAPandasTimestamp)
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
    date: PydanticTimestamp = Field(
        default_factory=lambda: Timestamp.now(tz=timezone.utc),
        unique=True,
        allow_mutation=False,
        sa_type=SAPandasTimestamp,
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
