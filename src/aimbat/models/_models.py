"""ORM classes representing AIMBAT data stored in the database."""

import os
import uuid
from collections.abc import Hashable
from datetime import timezone
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
from pandas import Timestamp
from pydantic import computed_field
from pydantic.alias_generators import to_camel
from sqlalchemy import Column, PickleType, func
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import column_property
from sqlmodel import Field, Relationship, SQLModel, col, select
from sqlmodel._compat import SQLModelConfig

from aimbat._types import (
    PydanticPositiveTimedelta,
    PydanticTimestamp,
    SAPandasTimedelta,
    SAPandasTimestamp,
)
from aimbat.io import DataType, read_seismogram_data, write_seismogram_data

from ._format import RichColSpec
from ._parameters import AimbatEventParametersBase, AimbatSeismogramParametersBase
from ._quality import (
    AimbatEventQualityBase,
    AimbatSeismogramQualityBase,
)

__all__ = [
    "AimbatTypes",
    "AimbatDataSource",
    "AimbatStation",
    "AimbatEvent",
    "AimbatEventParameters",
    "AimbatEventParametersSnapshot",
    "AimbatEventQuality",
    "AimbatEventQualitySnapshot",
    "AimbatSeismogram",
    "AimbatSeismogramParameters",
    "AimbatSeismogramParametersSnapshot",
    "AimbatSeismogramQuality",
    "AimbatSeismogramQualitySnapshot",
    "AimbatSnapshot",
]


class _AimbatDataSourceCreate(SQLModel):
    """Input model for creating a new data source entry."""

    sourcename: os.PathLike | str = Field(
        unique=True,
    )
    datatype: DataType = Field(
        default=DataType.SAC,
    )


class AimbatDataSource(SQLModel, table=True):
    """Class to store data source information."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        title="ID",
        description="Unique data source ID.",
        schema_extra={"rich": RichColSpec(style="yellow", highlight=False)},
    )
    sourcename: str = Field(
        title="Source name",
        description="Path or name of the data source.",
    )
    datatype: DataType = Field(
        default=DataType.SAC,
        title="Data type",
        description="Data type of the data source.",
    )
    seismogram_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatseismogram.id",
        ondelete="CASCADE",
        title="Seismogram ID",
        description="Foreign key referencing the parent seismogram.",
        schema_extra={"rich": RichColSpec(style="magenta", highlight=False)},
    )
    seismogram: "AimbatSeismogram" = Relationship(back_populates="datasource")
    "The seismogram this data source belongs to."


class AimbatSeismogramParameters(AimbatSeismogramParametersBase, table=True):
    """Processing parameters for a single seismogram."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        title="ID",
        description="Unique ID.",
    )
    seismogram_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatseismogram.id",
        ondelete="CASCADE",
        title="Seismogram ID",
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

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    seismogram_parameters_id: uuid.UUID = Field(
        foreign_key="aimbatseismogramparameters.id",
        ondelete="CASCADE",
        title="Seismogram parameters ID",
        description="Foreign key referencing the source seismogram parameters.",
    )
    parameters: AimbatSeismogramParameters = Relationship(back_populates="snapshots")
    "The seismogram parameters this snapshot was taken from."
    snapshot_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatsnapshot.id",
        ondelete="CASCADE",
        title="Snapshot ID",
        description="Foreign key referencing the parent snapshot.",
    )
    snapshot: "AimbatSnapshot" = Relationship(
        back_populates="seismogram_parameters_snapshots"
    )
    "The snapshot this record belongs to."


class AimbatEventParameters(AimbatEventParametersBase, table=True):
    """Processing parameters common to all seismograms of a particular event."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        title="ID",
        description="Unique ID.",
        schema_extra={
            "rich": RichColSpec(style="yellow", no_wrap=True, highlight=False)
        },
    )
    event_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatevent.id",
        ondelete="CASCADE",
        title="Event ID",
        description="Foreign key referencing the parent event.",
        schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False)
        },
    )
    event: "AimbatEvent" = Relationship(back_populates="parameters")
    "The event these parameters belong to."
    snapshots: list["AimbatEventParametersSnapshot"] = Relationship(
        back_populates="parameters", cascade_delete=True
    )
    "Parameter snapshots for this event."


class AimbatEventParametersSnapshot(AimbatEventParametersBase, table=True):
    """Snapshot of processing parameters for a particular event."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    snapshot_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatsnapshot.id",
        ondelete="CASCADE",
        title="Snapshot ID",
        description="Foreign key referencing the parent snapshot.",
    )
    parameters_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbateventparameters.id",
        ondelete="CASCADE",
        title="Event parameters ID",
        description="Foreign key referencing the source event parameters.",
    )
    snapshot: "AimbatSnapshot" = Relationship(
        back_populates="event_parameters_snapshot"
    )
    "The snapshot this record belongs to."
    parameters: AimbatEventParameters = Relationship(back_populates="snapshots")
    "The event parameters this snapshot was taken from."


class AimbatSeismogramQuality(AimbatSeismogramQualityBase, table=True):
    """Live quality metrics for a single seismogram.

    One row per seismogram. Updated in place whenever ICCS or MCCC runs.
    Fields are `None` until the corresponding algorithm has been executed.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    seismogram_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatseismogram.id",
        ondelete="CASCADE",
        title="Seismogram ID",
        description="Foreign key referencing the parent seismogram.",
    )
    seismogram: "AimbatSeismogram" = Relationship(back_populates="quality")
    "The seismogram these quality metrics belong to."
    snapshots: list["AimbatSeismogramQualitySnapshot"] = Relationship(
        back_populates="quality", cascade_delete=True
    )
    "Quality snapshots taken from this live record."


class AimbatSeismogramQualitySnapshot(AimbatSeismogramQualityBase, table=True):
    """Snapshot of quality metrics for a single seismogram."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    seismogram_quality_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatseismogramquality.id",
        ondelete="CASCADE",
        title="Seismogram quality ID",
        description="Foreign key referencing the source seismogram quality.",
    )
    quality: AimbatSeismogramQuality = Relationship(back_populates="snapshots")
    "The seismogram quality this snapshot was taken from."
    snapshot_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatsnapshot.id",
        ondelete="CASCADE",
        title="Snapshot ID",
        description="Foreign key referencing the parent snapshot.",
    )
    snapshot: "AimbatSnapshot" = Relationship(
        back_populates="seismogram_quality_snapshots"
    )
    "The snapshot this record belongs to."


class AimbatEventQuality(AimbatEventQualityBase, table=True):
    """Live quality metrics for a seismic event.

    One row per event. Updated in place whenever MCCC runs.
    Fields are `None` until MCCC has been executed.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    event_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatevent.id",
        ondelete="CASCADE",
        title="Event ID",
        description="Foreign key referencing the parent event.",
    )
    event: "AimbatEvent" = Relationship(back_populates="quality")
    "The event these quality metrics belong to."
    snapshots: list["AimbatEventQualitySnapshot"] = Relationship(
        back_populates="quality", cascade_delete=True
    )
    "Quality snapshots taken from this live record."


class AimbatEventQualitySnapshot(AimbatEventQualityBase, table=True):
    """Snapshot of quality metrics for a seismic event."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    event_quality_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbateventquality.id",
        ondelete="CASCADE",
        title="Event quality ID",
        description="Foreign key referencing the source event quality.",
    )
    quality: AimbatEventQuality = Relationship(back_populates="snapshots")
    "The event quality this snapshot was taken from."
    snapshot_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatsnapshot.id",
        ondelete="CASCADE",
        title="Snapshot ID",
        description="Foreign key referencing the parent snapshot.",
    )
    snapshot: "AimbatSnapshot" = Relationship(back_populates="event_quality_snapshot")
    "The snapshot this record belongs to."


class AimbatSnapshot(SQLModel, table=True):
    """Container for a point-in-time snapshot of event and seismogram parameters.

    The AimbatSnapshot class does not actually save any parameter data.
    It is used to keep track of the AimbatEventParametersSnapshot and
    AimbatSeismogramParametersSnapshot instances.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    time: PydanticTimestamp = Field(
        default_factory=lambda: Timestamp.now(tz=timezone.utc),
        unique=True,
        allow_mutation=False,
        sa_type=SAPandasTimestamp,
        title="Snapshot time",
        description="Timestamp when the snapshot was created.",
    )
    comment: str | None = Field(
        default=None, description="Optional comment for the snapshot."
    )
    parameters_hash: str | None = Field(
        default=None,
        title="Hash",
        description="SHA-256 hash of event and seismogram parameters at creation time.",
    )
    event_parameters_snapshot: AimbatEventParametersSnapshot = Relationship(
        back_populates="snapshot", cascade_delete=True
    )
    "Event parameter snapshot associated with this snapshot."
    seismogram_parameters_snapshots: list[AimbatSeismogramParametersSnapshot] = (
        Relationship(back_populates="snapshot", cascade_delete=True)
    )
    "Seismogram parameter snapshots associated with this snapshot."
    event_quality_snapshot: AimbatEventQualitySnapshot | None = Relationship(
        back_populates="snapshot", cascade_delete=True
    )
    "Event quality metric snapshot associated with this snapshot."
    seismogram_quality_snapshots: list[AimbatSeismogramQualitySnapshot] = Relationship(
        back_populates="snapshot", cascade_delete=True
    )
    "Seismogram quality metric snapshots associated with this snapshot."
    event_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatevent.id",
        ondelete="CASCADE",
        title="Event ID",
        description="Foreign key referencing the parent event.",
    )
    event: "AimbatEvent" = Relationship(back_populates="snapshots")
    "The event this snapshot belongs to."

    if TYPE_CHECKING:
        # defined as column properties below, but add same default values for type checking purposes
        seismogram_count: int = 0
        selected_seismogram_count: int = 0
        flipped_seismogram_count: int = 0


class AimbatSeismogram(SQLModel, table=True):
    """Class to store seismogram metadata."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    begin_time: PydanticTimestamp = Field(
        sa_type=SAPandasTimestamp,
        title="Begin time",
        description="Start time of the seismogram.",
    )
    delta: PydanticPositiveTimedelta = Field(
        sa_type=SAPandasTimedelta,
        title="Sampling interval",
        description="Sampling interval.",
    )
    t0: PydanticTimestamp = Field(
        sa_type=SAPandasTimestamp,
        title="Initial pick",
        description="Initial phase arrival pick.",
    )
    datasource: AimbatDataSource = Relationship(
        back_populates="seismogram", cascade_delete=True
    )
    "Data source for the seismogram waveform."
    station_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatstation.id",
        ondelete="CASCADE",
        title="Station ID",
        description="Foreign key referencing the recording station.",
    )
    station: "AimbatStation" = Relationship(back_populates="seismograms")
    "The station that recorded this seismogram."
    event_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatevent.id",
        ondelete="CASCADE",
        title="Event ID",
        description="Foreign key referencing the parent event.",
    )
    extra: dict[Hashable, Any] = Field(
        default_factory=dict,
        sa_column=Column(MutableDict.as_mutable(PickleType)),
        title="Extra metadata",
        description="Dictionary to store any additional metadata for the seismogram.",
    )
    event: "AimbatEvent" = Relationship(back_populates="seismograms")
    "The event this seismogram belongs to."
    parameters: "AimbatSeismogramParameters" = Relationship(
        back_populates="seismogram",
        cascade_delete=True,
    )
    "Processing parameters for this seismogram."
    quality: AimbatSeismogramQuality | None = Relationship(
        back_populates="seismogram",
        cascade_delete=True,
    )
    "Live quality metrics for this seismogram."

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

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(allow_mutation=False)
    network: str = Field(allow_mutation=False)
    location: str = Field(allow_mutation=False)
    channel: str = Field(allow_mutation=False)
    latitude: float
    longitude: float
    elevation: float | None = None
    seismograms: list[AimbatSeismogram] = Relationship(
        back_populates="station", cascade_delete=True
    )
    "Seismograms recorded at this station."

    if TYPE_CHECKING:
        # Column properties defined below, but add same default values for type checking purposes
        seismogram_count: int = 0
        event_count: int = 0


class AimbatEvent(SQLModel, table=True):
    """Class to store seismic event information."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    time: PydanticTimestamp = Field(
        unique=True, sa_type=SAPandasTimestamp, allow_mutation=False
    )
    latitude: float
    longitude: float
    depth: float | None = None
    last_modified: PydanticTimestamp | None = Field(
        default=None, sa_type=SAPandasTimestamp
    )
    seismograms: list[AimbatSeismogram] = Relationship(
        back_populates="event", cascade_delete=True
    )
    "List of seismograms of this event."

    parameters: AimbatEventParameters = Relationship(
        back_populates="event", cascade_delete=True
    )
    "Event parameters."

    quality: AimbatEventQuality | None = Relationship(
        back_populates="event", cascade_delete=True
    )
    "Live quality metrics for this event."

    snapshots: list[AimbatSnapshot] = Relationship(
        back_populates="event", cascade_delete=True
    )
    "List of snapshots."

    if TYPE_CHECKING:
        # Column properties defined below, but add same default values for type checking purposes
        seismogram_count: int = 0
        station_count: int = 0
        snapshot_count: int = 0


# ----------------------------------------------------------------------------
# Column properties
# ----------------------------------------------------------------------------

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

AimbatEvent.snapshot_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSnapshot.id)))
    .where(col(AimbatSnapshot.event_id) == col(AimbatEvent.id))
    .correlate_except(AimbatSnapshot)
    .scalar_subquery()
)
"Number of snapshots for this event."

AimbatStation.seismogram_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSeismogram.id)))
    .where(col(AimbatSeismogram.station_id) == col(AimbatStation.id))
    .correlate_except(AimbatSeismogram)
    .scalar_subquery()
)
"Number of seismograms recorded at this station."

AimbatStation.event_count = column_property(  # type: ignore[assignment]
    select(func.count(func.distinct(col(AimbatSeismogram.event_id))))
    .where(col(AimbatSeismogram.station_id) == col(AimbatStation.id))
    .correlate_except(AimbatSeismogram)
    .scalar_subquery()
)
"Number of unique events recorded at this station."

AimbatSnapshot.seismogram_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSeismogramParametersSnapshot.id)))
    .where(
        col(AimbatSeismogramParametersSnapshot.snapshot_id) == col(AimbatSnapshot.id)
    )
    .correlate_except(AimbatSeismogramParametersSnapshot)
    .scalar_subquery()
)
"Number of seismogram parameter snapshots associated with this snapshot."

AimbatSnapshot.selected_seismogram_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSeismogramParametersSnapshot.id)))
    .where(
        (col(AimbatSeismogramParametersSnapshot.snapshot_id) == col(AimbatSnapshot.id))
        & (col(AimbatSeismogramParametersSnapshot.select) == True)  # noqa: E712
    )
    .correlate_except(AimbatSeismogramParametersSnapshot)
    .scalar_subquery()
)
"Number of seismogram parameter snapshots associated with this snapshot that are marked as selected."

AimbatSnapshot.flipped_seismogram_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSeismogramParametersSnapshot.id)))
    .where(
        (col(AimbatSeismogramParametersSnapshot.snapshot_id) == col(AimbatSnapshot.id))
        & (col(AimbatSeismogramParametersSnapshot.flip) == True)  # noqa: E712
    )
    .correlate_except(AimbatSeismogramParametersSnapshot)
    .scalar_subquery()
)
"Number of seismogram parameter snapshots associated with this snapshot that are marked as flipped."


type AimbatTypes = (
    AimbatDataSource
    | AimbatStation
    | AimbatEvent
    | AimbatEventParameters
    | AimbatEventQuality
    | AimbatSeismogram
    | AimbatSeismogramParameters
    | AimbatSeismogramQuality
    | AimbatSnapshot
    | AimbatEventParametersSnapshot
    | AimbatEventQualitySnapshot
    | AimbatSeismogramParametersSnapshot
    | AimbatSeismogramQualitySnapshot
)
"""Union of all AIMBAT models that exist in the database."""
