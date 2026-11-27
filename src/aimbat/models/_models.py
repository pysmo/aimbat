"""ORM classes representing AIMBAT data stored in the database."""

import uuid
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
from pandas import Timestamp
from pydantic import model_validator
from pydantic.alias_generators import to_camel
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import class_mapper, column_property, object_session, undefer
from sqlmodel import Field, Relationship, SQLModel, col, select
from sqlmodel._compat import SQLModelConfig

from aimbat.io import DataType, read_seismogram_data, stage_seismogram_data
from aimbat.types import (
    PydanticPositiveTimedelta,
    PydanticTimestamp,
    SAPandasTimedelta,
    SAPandasTimestamp,
)

from ._format import RichColSpec
from ._parameters import AimbatPhaseParametersBase, AimbatSeismogramParametersBase
from ._quality import (
    AimbatPhaseQualityBase,
    AimbatSeismogramQualityBase,
)

__all__ = [
    "AimbatDataSource",
    "AimbatEvent",
    "AimbatNote",
    "AimbatPhase",
    "AimbatPhaseParameters",
    "AimbatPhaseParametersSnapshot",
    "AimbatPhaseQuality",
    "AimbatPhaseQualitySnapshot",
    "AimbatPick",
    "AimbatSeismogram",
    "AimbatSeismogramParameters",
    "AimbatSeismogramParametersSnapshot",
    "AimbatSeismogramQuality",
    "AimbatSeismogramQualitySnapshot",
    "AimbatSnapshot",
    "AimbatStation",
    "AimbatTypes",
    "PickOrigin",
    "channel_component",
    "phase_component",
    "phase_label",
    "undefer_counts",
]


def channel_component(channel: str) -> str | None:
    """Return the component letter of a SEED channel code, upper case.

    `None` when `channel` is not three letters or digits.
    """
    if len(channel) != 3 or not channel.isalnum() or not channel.isascii():
        return None
    return channel[-1].upper()


# A fixed length, so a longer `DataType` member needs no migration.
_DATATYPE_COLUMN = SAEnum(DataType, length=32, name="datatype")


class _AimbatDataSourceCreate(SQLModel):
    """Input model for creating a new data source entry."""

    sourcename: str = Field(
        unique=True,
    )
    datatype: DataType = Field(
        default=DataType.SAC,
    )


class AimbatDataSource(SQLModel, table=True):
    """Logical source identifier and format of the waveform data for a seismogram."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    # Named explicitly so `create_all` (via `create_project`) and the Alembic
    # migration that added it (`72c6b97febca`) produce an identically-named
    # constraint, keeping the two schema-creation paths in sync.
    __table_args__ = (
        UniqueConstraint("sourcename", name="uq_aimbatdatasource_sourcename"),
        Index("ix_aimbatdatasource_seismogram_id", "seismogram_id", unique=True),
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
        description=(
            "Opaque logical source identifier for the waveform data. "
            + "Uniqueness is enforced as plain string equality, not "
            + "canonicalised, so a file-based source reachable under two "
            + "different (but equivalent) path spellings is not recognised "
            + "as the same source - callers are responsible for "
            + "canonicalising before storing."
        ),
    )
    datatype: DataType = Field(
        default=DataType.SAC,
        sa_type=_DATATYPE_COLUMN,
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


class PickOrigin(StrEnum):
    """Where an initial pick came from."""

    SOURCE = auto()
    """Read from a data source or a picks source."""

    MANUAL = auto()
    """Entered by the user."""


class AimbatPick(SQLModel, table=True):
    """An initial pick as read or entered, before or after promotion.

    The raw record of a pick: its time, the label it was read with, the phase
    name assigned to it, where it came from, the target it was read with, and
    the seismogram it was matched to. Its time and label never change. A pick
    that is named and matched is promoted to the initial pick of a
    seismogram for a phase (an `AimbatSeismogramParameters` row referencing
    it).

    `event_id` is set only while the pick is unmatched and its event is
    known, so the picks of an event are those matched to its seismograms
    together with those whose `event_id` is the event's.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    __table_args__ = (
        Index(
            "ix_aimbatpick_source_name_source_key",
            "source_name",
            "source_key",
            unique=True,
            sqlite_where=text("source_name IS NOT NULL"),
        ),
        Index("ix_aimbatpick_seismogram_id", "seismogram_id"),
        Index(
            "ix_aimbatpick_event_id",
            "event_id",
            sqlite_where=text("event_id IS NOT NULL"),
        ),
        CheckConstraint(
            "(origin = 'SOURCE') = (source_name IS NOT NULL AND source_key IS NOT NULL)",
            name="aimbat_pick_source_provenance",
        ),
        CheckConstraint(
            "seismogram_id IS NULL OR event_id IS NULL",
            name="aimbat_pick_event_only_while_unmatched",
        ),
        CheckConstraint(
            "target_seismogram_id IS NULL OR (target_network IS NULL AND "
            + "target_station IS NULL AND target_location IS NULL AND "
            + "target_channel IS NULL AND target_event_time IS NULL)",
            name="aimbat_pick_one_target_form",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        title="ID",
        description="Unique pick ID.",
        schema_extra={"rich": RichColSpec(style="yellow", highlight=False)},
    )
    time: PydanticTimestamp = Field(
        sa_type=SAPandasTimestamp,
        title="Time",
        description="Pick time.",
    )
    label: str | None = Field(
        default=None,
        title="Label",
        description="Label the pick was read with, if any.",
    )
    phase_name: str | None = Field(
        default=None,
        title="Phase name",
        description="Phase name assigned to the pick, or `None` while unnamed.",
    )
    dismissed: bool = Field(
        default=False,
        title="Dismissed",
        description="Whether the pick is excluded from promotion and checks.",
    )
    origin: PickOrigin = Field(
        title="Origin",
        description="Where the pick came from.",
    )
    source_name: str | None = Field(
        default=None,
        title="Source name",
        description="Name of the source the pick was read from.",
    )
    source_type: DataType | None = Field(
        default=None,
        sa_type=_DATATYPE_COLUMN,
        title="Source type",
        description="Data type of the source the pick was read from.",
    )
    source_key: str | None = Field(
        default=None,
        title="Source key",
        description="Key identifying the pick within its source.",
    )
    target_network: str | None = Field(
        default=None,
        title="Target network",
        description="Network code of the target, as read.",
    )
    target_station: str | None = Field(
        default=None,
        title="Target station",
        description="Station code of the target, as read.",
    )
    target_location: str | None = Field(
        default=None,
        title="Target location",
        description="Location code of the target, as read.",
    )
    target_channel: str | None = Field(
        default=None,
        title="Target channel",
        description="Channel code of the target, as read. `None` matches any channel.",
    )
    target_event_time: PydanticTimestamp | None = Field(
        default=None,
        sa_type=SAPandasTimestamp,
        title="Target event time",
        description="Event origin time of the target, as read.",
    )
    target_seismogram_id: uuid.UUID | None = Field(
        default=None,
        title="Target seismogram ID",
        description="Seismogram ID of the target, as read.",
    )
    seismogram_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aimbatseismogram.id",
        ondelete="CASCADE",
        title="Seismogram ID",
        description="Seismogram the pick is matched to, or `None` while unmatched.",
        schema_extra={"rich": RichColSpec(style="magenta", highlight=False)},
    )
    event_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aimbatevent.id",
        ondelete="CASCADE",
        title="Event ID",
        description="Event of an unmatched pick, if known.",
        schema_extra={"rich": RichColSpec(style="magenta", highlight=False)},
    )
    # Many-to-one only. A collection on the seismogram would need
    # `passive_deletes="all"`, or deleting a seismogram would unmatch its
    # picks instead of letting the database delete them.
    seismogram: "AimbatSeismogram" = Relationship()
    "The seismogram the pick is matched to, if any."


class AimbatPhaseQuality(AimbatPhaseQualityBase, table=True):
    """Live quality metrics of a phase.

    One row per phase. Updated in place whenever MCCC runs.
    Fields are `None` until MCCC has been executed.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    __table_args__ = (Index("ix_aimbatphasequality_phase_id", "phase_id", unique=True),)

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    phase_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatphase.id",
        ondelete="CASCADE",
        title="Phase ID",
        description="Foreign key referencing the parent phase.",
    )
    mccc_fingerprint: str | None = Field(
        default=None,
        title="MCCC fingerprint",
        description="Digest of the parameters the MCCC results were computed from.",
    )
    phase: "AimbatPhase" = Relationship(back_populates="quality")
    "The phase these quality metrics belong to."
    snapshots: list["AimbatPhaseQualitySnapshot"] = Relationship(
        back_populates="quality", passive_deletes=True
    )
    "Quality snapshots taken from this live record."


class AimbatPhase(SQLModel, table=True):
    """A phase of one event, the unit of processing.

    Parameters, quality and snapshots belong to a phase, and so does the
    processing state of each seismogram (`AimbatSeismogramParameters`).
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "name",
            "component",
            name="uq_aimbatphase_event_id_name_component",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        title="ID",
        description="Unique phase ID.",
        schema_extra={"rich": RichColSpec(style="yellow", highlight=False)},
    )
    event_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatevent.id",
        ondelete="CASCADE",
        title="Event ID",
        description="Foreign key referencing the parent event.",
        schema_extra={"rich": RichColSpec(style="magenta", highlight=False)},
    )
    name: str = Field(
        max_length=32,
        title="Name",
        description="Phase name, unique within the event together with the component.",
    )
    component: str = Field(
        default="",
        max_length=32,
        sa_column_kwargs={"server_default": ""},
        title="Component",
        description=(
            "Component of the seismograms of the phase (`phase_component`), "
            + "empty when their channel codes have none."
        ),
    )
    event: "AimbatEvent" = Relationship(back_populates="phases")
    "The event this phase belongs to."
    parameters: "AimbatPhaseParameters" = Relationship(
        back_populates="phase", cascade_delete=True
    )
    "Processing parameters of the phase."
    quality: AimbatPhaseQuality | None = Relationship(
        back_populates="phase", cascade_delete=True
    )
    "Live quality metrics of the phase."
    seismogram_parameters: list["AimbatSeismogramParameters"] = Relationship(
        back_populates="phase", cascade_delete=True
    )
    "Processing state of each seismogram of the phase."
    snapshots: list["AimbatSnapshot"] = Relationship(
        back_populates="phase", cascade_delete=True
    )
    "Snapshots of the phase."

    if TYPE_CHECKING:
        # Column property defined below, but add same default value for type checking purposes
        snapshot_count: int = 0


class AimbatSeismogramQuality(AimbatSeismogramQualityBase, table=True):
    """Live quality metrics of one seismogram for one phase.

    One row per `AimbatSeismogramParameters` row. Updated in place whenever
    ICCS or MCCC runs. Fields are `None` until the corresponding algorithm
    has been executed.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    __table_args__ = (
        Index(
            "ix_aimbatseismogramquality_seismogram_parameters_id",
            "seismogram_parameters_id",
            unique=True,
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    seismogram_parameters_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatseismogramparameters.id",
        ondelete="CASCADE",
        title="Seismogram parameters ID",
        description="Foreign key referencing the seismogram's row for the phase.",
    )
    iccs_fingerprint: str | None = Field(
        default=None,
        title="ICCS fingerprint",
        description="Digest of the parameters `iccs_cc` was computed from.",
    )
    parameters: "AimbatSeismogramParameters" = Relationship(back_populates="quality")
    "The row these quality metrics belong to."


class AimbatSeismogramParameters(AimbatSeismogramParametersBase, table=True):
    """Processing state of one seismogram for one phase.

    A row exists only where the seismogram has an initial pick for the phase:
    it references that pick (`AimbatPick`), and reads the time through it.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "seismogram_id",
            "phase_id",
            name="uq_aimbatseismogramparameters_seismogram_id_phase_id",
        ),
        Index("ix_aimbatseismogramparameters_phase_id", "phase_id"),
        Index("ix_aimbatseismogramparameters_pick_id", "pick_id", unique=True),
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
        description="Foreign key referencing the seismogram.",
    )
    phase_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatphase.id",
        ondelete="CASCADE",
        title="Phase ID",
        description="Foreign key referencing the phase.",
    )
    pick_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatpick.id",
        ondelete="CASCADE",
        title="Pick ID",
        description="Foreign key referencing the initial pick.",
    )

    seismogram: "AimbatSeismogram" = Relationship(back_populates="phase_rows")
    "The seismogram."
    phase: AimbatPhase = Relationship(back_populates="seismogram_parameters")
    "The phase."
    pick: AimbatPick = Relationship()
    "The initial pick."
    quality: AimbatSeismogramQuality | None = Relationship(
        back_populates="parameters", cascade_delete=True
    )
    "Live quality metrics of the seismogram for the phase."
    snapshots: list["AimbatSeismogramParametersSnapshot"] = Relationship(
        back_populates="parameters", passive_deletes=True
    )
    "Snapshots taken from this row."

    @property
    def initial_pick(self) -> Timestamp:
        """Time of the initial pick."""
        return self.pick.time


class AimbatSeismogramParametersSnapshot(AimbatSeismogramParametersBase, table=True):
    """Snapshot of the processing state of one seismogram for one phase.

    Frozen history: the record keeps its own `seismogram_id` and outlives the
    seismogram it was taken from. `seismogram_parameters_id` is set to `NULL`
    if that live row is deleted. The initial pick is not frozen.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    seismogram_id: uuid.UUID | None = Field(
        default=None,
        title="Seismogram ID",
        description="ID of the seismogram this snapshot was taken from.",
    )
    seismogram_parameters_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aimbatseismogramparameters.id",
        ondelete="SET NULL",
        title="Seismogram parameters ID",
        description=(
            "Foreign key referencing the source seismogram parameters, or NULL if"
            + " it has been deleted."
        ),
    )
    parameters: AimbatSeismogramParameters | None = Relationship(
        back_populates="snapshots"
    )
    "The seismogram parameters this snapshot was taken from, if still present."
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


class AimbatPhaseParameters(AimbatPhaseParametersBase, table=True):
    """Processing parameters common to all seismograms of a phase."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    __table_args__ = (
        Index("ix_aimbatphaseparameters_phase_id", "phase_id", unique=True),
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
    phase_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatphase.id",
        ondelete="CASCADE",
        title="Phase ID",
        description="Foreign key referencing the parent phase.",
        schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False)
        },
    )
    phase: AimbatPhase = Relationship(back_populates="parameters")
    "The phase these parameters belong to."
    snapshots: list["AimbatPhaseParametersSnapshot"] = Relationship(
        back_populates="parameters", passive_deletes=True
    )
    "Parameter snapshots of this phase."


class AimbatPhaseParametersSnapshot(AimbatPhaseParametersBase, table=True):
    """Snapshot of the processing parameters of a phase.

    Frozen history: the source phase is still reachable via
    `snapshot.phase_id`, and `parameters_id` is set to `NULL` if the live
    parameter row is deleted.
    """

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
    parameters_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aimbatphaseparameters.id",
        ondelete="SET NULL",
        title="Phase parameters ID",
        description=(
            "Foreign key referencing the source phase parameters, or NULL if it "
            + "has been deleted."
        ),
    )
    snapshot: "AimbatSnapshot" = Relationship(
        back_populates="phase_parameters_snapshot"
    )
    "The snapshot this record belongs to."
    parameters: AimbatPhaseParameters | None = Relationship(back_populates="snapshots")
    "The phase parameters this snapshot was taken from, if still present."


class AimbatSeismogramQualitySnapshot(AimbatSeismogramQualityBase, table=True):
    """Snapshot of the quality metrics of one seismogram for one phase.

    Frozen history: the record keeps its own `seismogram_id` and outlives the
    seismogram it was taken from. `seismogram_parameters_id` is set to `NULL`
    if the live row it was taken from is deleted.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    seismogram_id: uuid.UUID | None = Field(
        default=None,
        title="Seismogram ID",
        description="ID of the seismogram this snapshot was taken from.",
    )
    seismogram_parameters_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aimbatseismogramparameters.id",
        ondelete="SET NULL",
        title="Seismogram parameters ID",
        description=(
            "Foreign key referencing the row the quality was taken from, or NULL"
            + " if it has been deleted."
        ),
    )
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


class AimbatPhaseQualitySnapshot(AimbatPhaseQualityBase, table=True):
    """Snapshot of the quality metrics of a phase.

    Frozen history: the source phase is still reachable via
    `snapshot.phase_id`, and `phase_quality_id` is set to `NULL` if the live
    quality row is deleted.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    phase_quality_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aimbatphasequality.id",
        ondelete="SET NULL",
        title="Phase quality ID",
        description=(
            "Foreign key referencing the source phase quality, or NULL if it has "
            + "been deleted."
        ),
    )
    quality: AimbatPhaseQuality | None = Relationship(back_populates="snapshots")
    "The phase quality this snapshot was taken from, if still present."
    snapshot_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatsnapshot.id",
        ondelete="CASCADE",
        title="Snapshot ID",
        description="Foreign key referencing the parent snapshot.",
    )
    snapshot: "AimbatSnapshot" = Relationship(back_populates="phase_quality_snapshot")
    "The snapshot this record belongs to."


class AimbatSnapshot(SQLModel, table=True):
    """Container for a point-in-time snapshot of a phase and its seismograms.

    An `AimbatSnapshot` does not store any parameter data itself. It is used
    to group and keep track of the associated `AimbatPhaseParametersSnapshot`
    and `AimbatSeismogramParametersSnapshot` instances.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "phase_id", "sequence", name="uq_aimbatsnapshot_phase_id_sequence"
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4, primary_key=True, description="Unique ID."
    )
    sequence: int = Field(
        title="Sequence",
        description="Monotonic per-phase counter; the definitive snapshot order.",
    )
    time: PydanticTimestamp = Field(
        default_factory=lambda: Timestamp.now("UTC"),
        sa_type=SAPandasTimestamp,
        title="Snapshot time",
        description="Timestamp when the snapshot was created.",
    )
    comment: str | None = Field(
        default=None, description="Optional comment for the snapshot."
    )
    automatic: bool = Field(
        default=False,
        description="Whether this snapshot was created automatically, e.g. by `data add`.",
    )
    mccc_hash: str | None = Field(
        default=None,
        title="MCCC hash",
        description=(
            "MCCC digest of the run whose results the snapshot froze, or None "
            + "if it froze none."
        ),
    )
    iccs_hash: str | None = Field(
        default=None,
        title="ICCS hash",
        description=("Instance digest of the phase's parameters at creation time."),
    )
    phase_parameters_snapshot: AimbatPhaseParametersSnapshot = Relationship(
        back_populates="snapshot", cascade_delete=True
    )
    "Phase parameter snapshot associated with this snapshot."
    seismogram_parameters_snapshots: list[AimbatSeismogramParametersSnapshot] = (
        Relationship(back_populates="snapshot", cascade_delete=True)
    )
    "Seismogram parameter snapshots associated with this snapshot."
    phase_quality_snapshot: AimbatPhaseQualitySnapshot | None = Relationship(
        back_populates="snapshot", cascade_delete=True
    )
    "Phase quality metric snapshot associated with this snapshot."
    seismogram_quality_snapshots: list[AimbatSeismogramQualitySnapshot] = Relationship(
        back_populates="snapshot", cascade_delete=True
    )
    "Seismogram quality metric snapshots associated with this snapshot."
    phase_id: uuid.UUID = Field(
        default=None,
        foreign_key="aimbatphase.id",
        ondelete="CASCADE",
        title="Phase ID",
        description="Foreign key referencing the parent phase.",
    )
    phase: AimbatPhase = Relationship(back_populates="snapshots")
    "The phase this snapshot belongs to."

    if TYPE_CHECKING:
        # defined as column properties below, but add same default values for type checking purposes
        seismogram_count: int = 0
        selected_seismogram_count: int = 0
        flipped_seismogram_count: int = 0


class AimbatSeismogram(SQLModel, table=True):
    """Seismogram metadata linking a recording station to an event.

    Holds timing information (`begin_time`, `delta`) and a reference to
    the waveform data source; the waveform samples themselves are not stored
    on this model but are read from that data source on demand.

    Reading `data` returns a read-only array. Assigning `data` stages the
    write in a per-session buffer and flushes it to the data source when the
    owning session commits (and discards it on rollback), mirroring how ORM
    column changes persist. Reads through the same session see the staged
    value before the commit; other sessions do not. In-place mutation
    (`seis.data[:] = ...`) is not supported. Assigning `data` on an instance
    attached to no session falls back to an immediate write.

    Exposes the pysmo [`Seismogram`][pysmo.Seismogram] interface directly
    (`begin_time`, `delta`, `data`, `end_time`). Processing state
    (`initial_pick`, `refined_pick`, `flip`, `select`) is not on this model:
    it lives on one `AimbatSeismogramParameters` row per phase, reached via
    `seismogram.phase_rows`.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )
    __table_args__ = (
        UniqueConstraint(
            "event_id", "station_id", name="uq_aimbatseismogram_event_id_station_id"
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        title="ID",
        description="Unique seismogram ID.",
        schema_extra={"rich": RichColSpec(style="yellow", highlight=False)},
    )
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
    event: "AimbatEvent" = Relationship(back_populates="seismograms")
    "The event this seismogram belongs to."
    phase_rows: list[AimbatSeismogramParameters] = Relationship(
        back_populates="seismogram",
        cascade_delete=True,
    )
    "Processing state of this seismogram, one row per phase."

    if TYPE_CHECKING:
        # `data` and `end_time` are provided at runtime by the properties in
        # the `else` branch; declared here so type checkers see them as
        # attributes of the model.
        data: npt.NDArray[np.floating] = np.array([])

        @property
        def end_time(self) -> Timestamp: ...

    else:

        @property
        def end_time(self) -> Timestamp:
            """End time of the seismogram, derived from begin_time, delta, and data length.

            A plain property rather than a `computed_field`: evaluating it reads
            the full waveform to count samples, so it must not be pulled into
            `model_dump()` / serialisation. Matches `pysmo.Seismogram.end_time`.
            """
            if len(self.data) == 0:
                return self.begin_time
            return self.begin_time + self.delta * (len(self.data) - 1)

        @property
        def data(self) -> npt.NDArray[np.floating]:
            """Seismogram waveform data as a read-only array.

            Assigning to this attribute stages the write; it reaches the data
            source when the owning session commits (see the class docstring).

            In-place mutation (`seis.data[:] = ...`) is not supported - the
            setter has no way to intercept a slice assignment on the array it
            already returned, so NumPy raises its own `ValueError:
            assignment destination is read-only` rather than a message
            specific to this class. Assign a new array to `seis.data` instead.
            """
            if self.datasource is None:
                raise ValueError("Expected a valid datasource name, got None.")
            return read_seismogram_data(
                self.datasource.sourcename,
                self.datasource.datatype,
                object_session(self),
            )

        @data.setter
        def data(self, value: npt.NDArray[np.floating]) -> None:
            if self.datasource is None:
                raise ValueError("Expected a valid datasource name, got None.")
            stage_seismogram_data(
                object_session(self),
                self.datasource.sourcename,
                self.datasource.datatype,
                value,
            )


class AimbatStation(SQLModel, table=True):
    """One recording stream, identified by its network, station, location and channel codes."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )
    __table_args__ = (
        UniqueConstraint(
            "network",
            "name",
            "location",
            "channel",
            name="uq_aimbatstation_network_name_location_channel",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        title="ID",
        description="Unique station ID.",
        schema_extra={"rich": RichColSpec(style="yellow", highlight=False)},
    )
    name: str = Field(
        title="Name",
        description="Station name (SEED station code).",
    )
    network: str = Field(
        title="Network",
        description="Network code.",
    )
    location: str = Field(
        title="Location",
        description="Location code.",
    )
    channel: str = Field(
        title="Channel",
        description="Channel code (e.g. BHZ).",
    )
    latitude: float = Field(
        title="Latitude", description="Station latitude in degrees."
    )
    longitude: float = Field(
        title="Longitude", description="Station longitude in degrees."
    )
    elevation: float | None = Field(
        default=None, title="Elevation", description="Station elevation in metres."
    )
    seismograms: list[AimbatSeismogram] = Relationship(
        back_populates="station", cascade_delete=True
    )
    "Seismograms recorded at this station."

    @property
    def component(self) -> str | None:
        """Component letter of the channel code (Z, N, E, 1, 2, R, T, ...).

        `None` when the channel code is not three letters or digits.
        """
        return channel_component(self.channel)

    if TYPE_CHECKING:
        # Column properties defined below, but add same default values for type checking purposes
        seismogram_count: int = 0
        event_count: int = 0


def phase_component(station: AimbatStation) -> str:
    """Return the component of the phases a station's seismograms belong to.

    Seismograms of one event, phase name and component share a phase. The
    component is the station's `component`, or empty when its channel code
    has none.
    """
    return station.component or ""


def phase_label(name: str, component: str) -> str:
    """Return a phase's name and component for display: `SKS (Q)`, or `SKS` without a component."""
    return f"{name} ({component})" if component else name


class AimbatEvent(SQLModel, table=True):
    """Seismic event with origin time, location, and depth."""

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        title="ID",
        description="Unique event ID.",
        schema_extra={"rich": RichColSpec(style="yellow", highlight=False)},
    )
    time: PydanticTimestamp = Field(
        unique=True,
        sa_type=SAPandasTimestamp,
        title="Time",
        description="Event origin time (UTC).",
    )
    latitude: float = Field(title="Latitude", description="Event latitude in degrees.")
    longitude: float = Field(
        title="Longitude", description="Event longitude in degrees."
    )
    depth: float | None = Field(
        default=None, title="Depth", description="Event depth in metres."
    )
    seismograms: list[AimbatSeismogram] = Relationship(
        back_populates="event", cascade_delete=True
    )
    "List of seismograms of this event."

    phases: list[AimbatPhase] = Relationship(
        back_populates="event", cascade_delete=True
    )
    "Phases of this event."

    if TYPE_CHECKING:
        # Column properties defined below, but add same default values for type checking purposes
        seismogram_count: int = 0
        site_count: int = 0
        phase_count: int = 0
        snapshot_count: int = 0


# ----------------------------------------------------------------------------
# Column properties
#
# Each of these is a correlated scalar subquery, and all are `deferred` so
# that they are left out of an ordinary SELECT of the owning model -
# AimbatEvent carries four, and the processing paths that load an event to
# run ICCS never read any of them. Reading one on a loaded instance emits its
# subquery on its own, so the paths that render counts for many rows (the
# `dump_*_table` functions feeding the read models) undefer them to keep that
# a single query.
# ----------------------------------------------------------------------------

AimbatEvent.seismogram_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSeismogram.id)))
    .where(col(AimbatSeismogram.event_id) == col(AimbatEvent.id))
    .correlate_except(AimbatSeismogram)
    .scalar_subquery(),
    deferred=True,
)
"Number of seismograms for this event."

# "." occurs in neither code, so the joined pair is unambiguous.
AimbatEvent.site_count = column_property(  # type: ignore[assignment]
    select(
        func.count(
            func.distinct(col(AimbatStation.network) + "." + col(AimbatStation.name))
        )
    )
    .select_from(AimbatSeismogram)
    .join(AimbatStation)
    .where(col(AimbatSeismogram.event_id) == col(AimbatEvent.id))
    .correlate_except(AimbatSeismogram, AimbatStation)
    .scalar_subquery(),
    deferred=True,
)
"Number of sites (network and station code) with seismograms for this event."

AimbatEvent.phase_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatPhase.id)))
    .where(col(AimbatPhase.event_id) == col(AimbatEvent.id))
    .correlate_except(AimbatPhase)
    .scalar_subquery(),
    deferred=True,
)
"Number of phases of this event."

AimbatEvent.snapshot_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSnapshot.id)))
    .join(AimbatPhase, col(AimbatPhase.id) == col(AimbatSnapshot.phase_id))
    .where(col(AimbatPhase.event_id) == col(AimbatEvent.id))
    .correlate_except(AimbatSnapshot, AimbatPhase)
    .scalar_subquery(),
    deferred=True,
)
"Number of snapshots of all phases of this event."

AimbatPhase.snapshot_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSnapshot.id)))
    .where(col(AimbatSnapshot.phase_id) == col(AimbatPhase.id))
    .correlate_except(AimbatSnapshot)
    .scalar_subquery(),
    deferred=True,
)
"Number of snapshots of this phase."

AimbatStation.seismogram_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSeismogram.id)))
    .where(col(AimbatSeismogram.station_id) == col(AimbatStation.id))
    .correlate_except(AimbatSeismogram)
    .scalar_subquery(),
    deferred=True,
)
"Number of seismograms recorded at this station."

AimbatStation.event_count = column_property(  # type: ignore[assignment]
    select(func.count(func.distinct(col(AimbatSeismogram.event_id))))
    .where(col(AimbatSeismogram.station_id) == col(AimbatStation.id))
    .correlate_except(AimbatSeismogram)
    .scalar_subquery(),
    deferred=True,
)
"Number of unique events recorded at this station."

AimbatSnapshot.seismogram_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSeismogramParametersSnapshot.id)))
    .where(
        col(AimbatSeismogramParametersSnapshot.snapshot_id) == col(AimbatSnapshot.id)
    )
    .correlate_except(AimbatSeismogramParametersSnapshot)
    .scalar_subquery(),
    deferred=True,
)
"Number of seismogram parameter snapshots associated with this snapshot."

AimbatSnapshot.selected_seismogram_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSeismogramParametersSnapshot.id)))
    .where(
        (col(AimbatSeismogramParametersSnapshot.snapshot_id) == col(AimbatSnapshot.id))
        & col(AimbatSeismogramParametersSnapshot.select).is_(True)
    )
    .correlate_except(AimbatSeismogramParametersSnapshot)
    .scalar_subquery(),
    deferred=True,
)
(
    "Number of seismogram parameter snapshots associated with this "
    + "snapshot that are marked as selected."
)

AimbatSnapshot.flipped_seismogram_count = column_property(  # type: ignore[assignment]
    select(func.count(col(AimbatSeismogramParametersSnapshot.id)))
    .where(
        (col(AimbatSeismogramParametersSnapshot.snapshot_id) == col(AimbatSnapshot.id))
        & col(AimbatSeismogramParametersSnapshot.flip).is_(True)
    )
    .correlate_except(AimbatSeismogramParametersSnapshot)
    .scalar_subquery(),
    deferred=True,
)
(
    "Number of seismogram parameter snapshots associated with this "
    + "snapshot that are marked as flipped."
)


def undefer_counts(model_class: type[SQLModel]) -> tuple[Any, ...]:
    """Loader options that fetch `model_class`'s count columns in the main query.

    Pass these to `select(...).options(...)` in a path that renders counts for
    many rows; without them each count is a query of its own, per row.

    The options are read off the mapper rather than listed here, so a count
    added later reaches every table-rendering path without any of them being
    touched.
    """
    return tuple(
        undefer(getattr(model_class, prop.key))
        for prop in class_mapper(model_class).column_attrs
        if prop.deferred
    )


class AimbatNote(SQLModel, table=True):
    """Free-text Markdown note attached to an event, station, seismogram, or snapshot.

    Exactly one of the four FK fields is set per row, and at most one note
    exists per parent record (enforced by the per-FK partial unique indexes).
    Deletion of the parent record cascades to delete the note via the DB-level
    foreign key constraint.
    """

    model_config = SQLModelConfig(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    __table_args__ = (
        CheckConstraint(
            (
                "(CASE WHEN event_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN "
                + "station_id IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN seismogram_id "
                + "IS NOT NULL THEN 1 ELSE 0 END + CASE WHEN snapshot_id IS NOT NULL "
                + "THEN 1 ELSE 0 END) = 1"
            ),
            name="aimbat_note_exactly_one_parent",
        ),
        Index(
            "ix_aimbatnote_event_id",
            "event_id",
            unique=True,
            sqlite_where=text("event_id IS NOT NULL"),
        ),
        Index(
            "ix_aimbatnote_station_id",
            "station_id",
            unique=True,
            sqlite_where=text("station_id IS NOT NULL"),
        ),
        Index(
            "ix_aimbatnote_seismogram_id",
            "seismogram_id",
            unique=True,
            sqlite_where=text("seismogram_id IS NOT NULL"),
        ),
        Index(
            "ix_aimbatnote_snapshot_id",
            "snapshot_id",
            unique=True,
            sqlite_where=text("snapshot_id IS NOT NULL"),
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        description="Unique note ID.",
    )
    content: str = Field(
        default="",
        description="Note content in Markdown format.",
    )
    event_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aimbatevent.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent event.",
    )
    station_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aimbatstation.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent station.",
    )
    seismogram_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aimbatseismogram.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent seismogram.",
    )
    snapshot_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="aimbatsnapshot.id",
        ondelete="CASCADE",
        description="Foreign key referencing the parent snapshot.",
    )

    @model_validator(mode="after")
    def _exactly_one_parent(self) -> "AimbatNote":
        # Table-model __init__ skips Pydantic validation, so this never runs
        # on the normal construction path; the DB CheckConstraint above is
        # the real guard. Kept for the direct-Pydantic-construction case.
        set_count = sum(
            fk is not None
            for fk in (
                self.event_id,
                self.station_id,
                self.seismogram_id,
                self.snapshot_id,
            )
        )
        if set_count != 1:
            raise ValueError(
                "Exactly one of event_id, station_id, seismogram_id, snapshot_id must"
                + " be set on AimbatNote."
            )
        return self


type AimbatTypes = (
    AimbatDataSource
    | AimbatNote
    | AimbatStation
    | AimbatEvent
    | AimbatPhase
    | AimbatPhaseParameters
    | AimbatPhaseQuality
    | AimbatPick
    | AimbatSeismogram
    | AimbatSeismogramParameters
    | AimbatSeismogramQuality
    | AimbatSnapshot
    | AimbatPhaseParametersSnapshot
    | AimbatPhaseQualitySnapshot
    | AimbatSeismogramParametersSnapshot
    | AimbatSeismogramQualitySnapshot
)
"""Union of all AIMBAT models that exist in the database."""
