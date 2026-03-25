from __future__ import annotations

from typing import TYPE_CHECKING, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from aimbat._types import PydanticTimedelta, PydanticTimestamp
from aimbat.logger import logger
from aimbat.utils import mean_and_sem, mean_and_sem_timedelta
from aimbat.utils.formatters import fmt_depth_km, fmt_flip

from ._format import RichColSpec, TuiColSpec

if TYPE_CHECKING:
    from sqlmodel import Session

    from ._models import (
        AimbatEvent,
        AimbatSeismogram,
        AimbatSeismogramParametersSnapshot,
        AimbatSeismogramQualitySnapshot,
        AimbatSnapshot,
        AimbatStation,
    )

__all__ = [
    "AimbatEventRead",
    "AimbatSeismogramRead",
    "SeismogramQualityStats",
    "AimbatSnapshotRead",
    "AimbatStationRead",
    "SnapshotSeismogramResult",
    "SnapshotResults",
]


class SeismogramQualityStats(BaseModel):
    """Aggregated seismogram quality statistics for an event or station.

    Built from live quality records. All mean fields are `None` when no
    seismograms in the group have quality data. SEM fields are `None` when
    fewer than two values are available. `mccc_rmse` is only populated by
    `from_event` and `from_snapshot`; it is always `None` for `from_station`.
    `event_id` is populated by `from_event` and `from_snapshot`; it is always
    `None` for `from_station`.
    """

    model_config = ConfigDict(frozen=True)

    event_id: UUID | None = Field(
        default=None,
        title="Event ID",
        json_schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    snapshot_id: UUID | None = Field(
        default=None,
        title="Snapshot ID",
        json_schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    station_id: UUID | None = Field(
        default=None,
        title="Station ID",
        json_schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    count: int = Field(title="Count")
    cc_mean: float | None = Field(default=None, title="ICCS CC mean")
    cc_mean_sem: float | None = Field(default=None, title="ICCS CC mean SEM")
    mccc_cc_mean: float | None = Field(default=None, title="MCCC CC mean")
    mccc_cc_mean_sem: float | None = Field(default=None, title="MCCC CC mean SEM")
    mccc_cc_std: float | None = Field(default=None, title="MCCC CC std")
    mccc_cc_std_sem: float | None = Field(default=None, title="MCCC CC std SEM")
    mccc_error: PydanticTimedelta | None = Field(default=None, title="MCCC error")
    mccc_error_sem: PydanticTimedelta | None = Field(
        default=None, title="MCCC error SEM"
    )
    mccc_rmse: PydanticTimedelta | None = Field(default=None, title="MCCC RMSE")

    @classmethod
    def from_event(cls, event: AimbatEvent) -> Self:
        """Build quality stats from live quality records for an event.

        Aggregates `iccs_cc` and MCCC metrics across all seismograms that
        have live quality records. `mccc_rmse` is taken from the event-level
        quality record.

        Warning:
            This method may trigger lazy-loading of `event.seismograms` and
            each `seis.quality` relationship. For performance, query `event`
            with `selectinload` for `seismograms` and their nested `quality`
            relationships before calling.

        Args:
            event: The event whose seismograms' live quality to aggregate.

        Returns:
            Aggregated quality statistics.
        """
        logger.debug(f"Building quality stats for event {event.id}.")
        qualities = [
            seis.quality for seis in event.seismograms if seis.quality is not None
        ]

        cc_mean, cc_mean_sem = mean_and_sem(
            [q.iccs_cc for q in qualities if q.iccs_cc is not None]
        )
        mccc_cc_mean, mccc_cc_mean_sem = mean_and_sem(
            [q.mccc_cc_mean for q in qualities if q.mccc_cc_mean is not None]
        )
        mccc_cc_std, mccc_cc_std_sem = mean_and_sem(
            [q.mccc_cc_std for q in qualities if q.mccc_cc_std is not None]
        )
        mccc_error, mccc_error_sem = mean_and_sem_timedelta(
            [q.mccc_error for q in qualities if q.mccc_error is not None]
        )
        mccc_rmse = event.quality.mccc_rmse if event.quality is not None else None

        return cls(
            event_id=event.id,
            count=len(event.seismograms),
            cc_mean=cc_mean,
            cc_mean_sem=cc_mean_sem,
            mccc_cc_mean=mccc_cc_mean,
            mccc_cc_mean_sem=mccc_cc_mean_sem,
            mccc_cc_std=mccc_cc_std,
            mccc_cc_std_sem=mccc_cc_std_sem,
            mccc_error=mccc_error,
            mccc_error_sem=mccc_error_sem,
            mccc_rmse=mccc_rmse,
        )

    @classmethod
    def from_station(cls, station: AimbatStation) -> Self:
        """Build quality stats from live quality records for a station.

        Aggregates `iccs_cc` and MCCC metrics across all seismograms at the
        station that have live quality records.

        Warning:
            This method may trigger lazy-loading of `station.seismograms` and
            each `seis.quality` relationship. For performance, query `station`
            with `selectinload` for `seismograms` and their nested `quality`
            relationships before calling.

        Args:
            station: The station whose seismograms' live quality to aggregate.

        Returns:
            Aggregated quality statistics. `mccc_rmse` is always `None`.
        """
        logger.debug(f"Building quality stats for station {station.id}.")
        qualities = [
            seis.quality for seis in station.seismograms if seis.quality is not None
        ]

        cc_mean, cc_mean_sem = mean_and_sem(
            [q.iccs_cc for q in qualities if q.iccs_cc is not None]
        )
        mccc_cc_mean, mccc_cc_mean_sem = mean_and_sem(
            [q.mccc_cc_mean for q in qualities if q.mccc_cc_mean is not None]
        )
        mccc_cc_std, mccc_cc_std_sem = mean_and_sem(
            [q.mccc_cc_std for q in qualities if q.mccc_cc_std is not None]
        )
        mccc_error, mccc_error_sem = mean_and_sem_timedelta(
            [q.mccc_error for q in qualities if q.mccc_error is not None]
        )

        return cls(
            station_id=station.id,
            count=len(station.seismograms),
            cc_mean=cc_mean,
            cc_mean_sem=cc_mean_sem,
            mccc_cc_mean=mccc_cc_mean,
            mccc_cc_mean_sem=mccc_cc_mean_sem,
            mccc_cc_std=mccc_cc_std,
            mccc_cc_std_sem=mccc_cc_std_sem,
            mccc_error=mccc_error,
            mccc_error_sem=mccc_error_sem,
            mccc_rmse=None,
        )

    @classmethod
    def from_snapshot(cls, snapshot: AimbatSnapshot) -> Self:
        """Build quality stats from the frozen quality records in a snapshot.

        Aggregates from `AimbatSeismogramQualitySnapshot` records rather than
        live quality, so the result reflects the state at snapshot time.

        Args:
            snapshot: The snapshot to aggregate quality from.

        Returns:
            Aggregated quality statistics.
        """
        logger.debug(f"Building quality stats for snapshot {snapshot.id}.")
        records = snapshot.seismogram_quality_snapshots

        cc_mean, cc_mean_sem = mean_and_sem(
            [r.iccs_cc for r in records if r.iccs_cc is not None]
        )
        mccc_cc_mean, mccc_cc_mean_sem = mean_and_sem(
            [r.mccc_cc_mean for r in records if r.mccc_cc_mean is not None]
        )
        mccc_cc_std, mccc_cc_std_sem = mean_and_sem(
            [r.mccc_cc_std for r in records if r.mccc_cc_std is not None]
        )
        mccc_error, mccc_error_sem = mean_and_sem_timedelta(
            [r.mccc_error for r in records if r.mccc_error is not None]
        )
        eq = snapshot.event_quality_snapshot
        mccc_rmse = eq.mccc_rmse if eq is not None else None

        return cls(
            event_id=snapshot.event_id,
            snapshot_id=snapshot.id,
            count=snapshot.seismogram_count,
            cc_mean=cc_mean,
            cc_mean_sem=cc_mean_sem,
            mccc_cc_mean=mccc_cc_mean,
            mccc_cc_mean_sem=mccc_cc_mean_sem,
            mccc_cc_std=mccc_cc_std,
            mccc_cc_std_sem=mccc_cc_std_sem,
            mccc_error=mccc_error,
            mccc_error_sem=mccc_error_sem,
            mccc_rmse=mccc_rmse,
        )


class AimbatEventRead(BaseModel):
    """Read model for AimbatEvent including computed counts."""

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: UUID = Field(
        title="ID",
        description="Unique identifier for the event",
        json_schema_extra={
            "rich": RichColSpec(style="yellow"),  # type: ignore[dict-item]
        },
    )
    short_id: str | None = Field(
        default=None,
        title="Short ID",
        description="Shortened unique identifier",
        json_schema_extra={
            "tui": TuiColSpec(display_title="ID"),  # type: ignore[dict-item]
            "rich": RichColSpec(display_title="ID", style="yellow", highlight=False),  # type: ignore[dict-item]
        },
    )
    completed: bool = Field(
        title="Completed",
        description="Indicates if the event's parameters are marked as completed",
        json_schema_extra={"tui": TuiColSpec(text_align="center")},  # type: ignore[dict-item]
    )
    time: PydanticTimestamp = Field(
        title="Event time",
        description="Origin time of the event",
    )
    latitude: float = Field(
        title="Latitude",
        description="Latitude of the event",
    )
    longitude: float = Field(
        title="Longitude",
        description="Longitude of the event",
    )
    depth: float | None = Field(
        title="Depth",
        description="Depth of the event",
        json_schema_extra={
            "tui": TuiColSpec(display_title="Depth km", formatter=fmt_depth_km),  # type: ignore[dict-item]
            "rich": RichColSpec(
                display_title=r"Depth \[km]", justify="right", formatter=fmt_depth_km
            ),  # type: ignore[dict-item]
        },
    )
    seismogram_count: int = Field(
        title="Seismograms",
        description="Number of seismograms associated with this event",
    )
    station_count: int = Field(
        title="Stations",
        description="Number of stations associated with this event",
    )
    snapshot_count: int = Field(
        title="Snapshots",
        description="Number of snapshots associated with this event",
    )
    last_modified: PydanticTimestamp | None = Field(
        default=None,
        title="Last modified",
        description="Timestamp of the last modification of this event's parameters",
    )

    @classmethod
    def from_event(cls, event: "AimbatEvent", session: "Session | None" = None) -> Self:
        """Create an AimbatEventRead from an AimbatEvent ORM instance."""
        data = event.model_dump()

        if session is not None:
            from aimbat.utils import uuid_shortener

            data["short_id"] = uuid_shortener(session, event)

        data.update(
            {
                "completed": event.parameters.completed if event.parameters else False,
                "seismogram_count": event.seismogram_count or 0,
                "station_count": event.station_count or 0,
                "snapshot_count": event.snapshot_count or 0,
            }
        )
        return cls(**data)


class AimbatStationRead(BaseModel):
    """Read model for AimbatStation including parameters."""

    model_config = ConfigDict(
        frozen=True, alias_generator=to_camel, populate_by_name=True
    )

    id: UUID = Field(
        title="ID",
        description="Unique identifier for the station",
        json_schema_extra={
            "rich": RichColSpec(style="yellow", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    short_id: str | None = Field(
        default=None,
        title="Short ID",
        description="Shortened unique identifier",
        json_schema_extra={
            "tui": TuiColSpec(display_title="ID"),  # type: ignore[dict-item]
            "rich": RichColSpec(
                display_title="ID", style="yellow", no_wrap=True, highlight=False
            ),  # type: ignore[dict-item]
        },
    )
    network: str = Field(title="Network", description="Station network code")
    name: str = Field(title="Name", description="Station name")
    location: str | None = Field(title="Location", description="Station location code")
    channel: str = Field(title="Channel", description="Station channel code")
    latitude: float = Field(title="Latitude", description="Station latitude")
    longitude: float = Field(title="Longitude", description="Station longitude")
    elevation: float | None = Field(
        default=None,
        title="Elevation",
        description="Station elevation",
        json_schema_extra={"tui": TuiColSpec(formatter=lambda x: str(int(x)))},  # type: ignore[dict-item]
    )

    cc_mean: float | None = Field(
        default=None,
        title="Stack CC (mean)",
        description="Mean cross-correlation coefficient at this station",
    )

    cc_sem: float | None = Field(
        default=None,
        title="Stack CC (SEM)",
        description="Standard error of the mean of cross-correlation coefficients at this station",
    )

    seismogram_count: int = Field(
        title="Seismogram count",
        description="Number of seismograms associated with this station",
    )

    event_count: int = Field(
        title="Event count",
        description="Number of unique events recorded at this station",
    )

    @classmethod
    def from_station(
        cls,
        station: AimbatStation,
        session: Session | None = None,
    ) -> Self:
        data = station.model_dump()

        if session is not None:
            from aimbat.utils import uuid_shortener

            data["short_id"] = uuid_shortener(session, station)
            iccs_ccs = tuple(
                seis.quality.iccs_cc
                for seis in station.seismograms
                if seis.quality is not None and seis.quality.iccs_cc is not None
            )
            data["cc_mean"], data["cc_sem"] = mean_and_sem(iccs_ccs)

        data.update(
            {
                "seismogram_count": station.seismogram_count or 0,
                "event_count": station.event_count or 0,
            }
        )
        return cls(**data)


class AimbatSeismogramRead(BaseModel):
    """Read model for AimbatSeismogram including parameters."""

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: UUID = Field(
        title="ID",
        description="Unique identifier for the seismogram",
        json_schema_extra={
            "rich": RichColSpec(style="yellow", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    short_id: str | None = Field(
        default=None,
        title="Short ID",
        description="Shortened unique identifier",
        json_schema_extra={
            "tui": TuiColSpec(display_title="ID"),  # type: ignore[dict-item]
            "rich": RichColSpec(
                display_title="ID", style="yellow", no_wrap=True, highlight=False
            ),  # type: ignore[dict-item]
        },
    )
    name: str = Field(title="Name", description="Name of the seismogram.")

    channel: str = Field(
        title="Channel",
        description="Seismogram channel.",
    )

    select: bool = Field(
        title="Select",
        description="Whether the seismogram is selected for processing.",
        json_schema_extra={"tui": TuiColSpec(text_align="center")},  # type: ignore[dict-item]
    )

    flip: bool = Field(
        title="Flip",
        description="Whether the seismogram is flipped for processing.",
        json_schema_extra={
            "tui": TuiColSpec(text_align="center", formatter=fmt_flip),  # type: ignore[dict-item]
            "rich": RichColSpec(formatter=fmt_flip),  # type: ignore[dict-item]
        },
    )

    delta_t: PydanticTimedelta | None = Field(
        title="Δt (s)",
        description="Arrival time residual (observed - predicted) in seconds.",
    )

    mccc_error: PydanticTimedelta | None = Field(
        title="MCCC err Δt (s)",
        description="Uncertainty in the MCCC arrival time residual (observed - predicted) in seconds.",
    )

    iccs_cc: float | None = Field(
        title="Stack CC",
        description="Cross-correlation coefficient with ICCS stack.",
    )

    mccc_cc_mean: float | None = Field(
        title="MCCC CC",
        description="Mean cross-correlation coefficient of MCCC cluster.",
    )

    mccc_cc_std: float | None = Field(
        title="MCCC CC std",
        description="Standard deviation of cross-correlation coefficients in MCCC cluster.",
    )

    event_id: UUID = Field(
        title="Event ID",
        description="ID of the associated event.",
        json_schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )

    short_event_id: str | None = Field(
        title="Short Event ID",
        description="Shortened unique identifier for the associated event.",
        json_schema_extra={
            "rich": RichColSpec(
                display_title="Event ID", style="magenta", no_wrap=True, highlight=False
            ),  # type: ignore[dict-item]
        },
    )

    @classmethod
    def from_seismogram(
        cls, seismogram: AimbatSeismogram, session: Session | None = None
    ) -> Self:
        name = (f"{seismogram.station.network}." or "") + seismogram.station.name

        short_id = None
        short_event_id = None
        if session is not None:
            from aimbat.utils import uuid_shortener

            short_id = uuid_shortener(session, seismogram)
            short_event_id = uuid_shortener(session, seismogram.event)

        delta_t = (
            seismogram.parameters.t1 - seismogram.t0
            if seismogram.parameters.t1
            else None
        )
        return cls(
            id=seismogram.id,
            short_id=short_id,
            name=name,
            channel=seismogram.station.channel,
            select=seismogram.parameters.select,
            flip=seismogram.parameters.flip,
            delta_t=delta_t,
            mccc_error=getattr(seismogram.quality, "mccc_error", None),
            iccs_cc=getattr(seismogram.quality, "iccs_cc", None),
            mccc_cc_mean=getattr(seismogram.quality, "mccc_cc_mean", None),
            mccc_cc_std=getattr(seismogram.quality, "mccc_cc_std", None),
            event_id=seismogram.event_id,
            short_event_id=short_event_id,
        )


class AimbatSnapshotRead(BaseModel):
    """Read model for AimbatSnapshot with a seismogram count."""

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: UUID = Field(
        title="ID",
        description="Unique identifier for the snapshot",
        json_schema_extra={
            "rich": RichColSpec(style="yellow", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    short_id: str | None = Field(
        default=None,
        title="Short ID",
        description="Shortened unique identifier",
        json_schema_extra={
            "tui": TuiColSpec(display_title="ID"),  # type: ignore[dict-item]
            "rich": RichColSpec(
                display_title="ID", style="yellow", no_wrap=True, highlight=False
            ),  # type: ignore[dict-item]
        },
    )
    time: PydanticTimestamp = Field(
        title="Time", description="Timestamp of the snapshot"
    )
    comment: str | None = Field(
        title="Comment", description="Optional comment for the snapshot"
    )
    seismogram_count: int = Field(
        title="Seismograms",
        description="Total number of seismograms in the snapshot",
    )
    selected_seismogram_count: int = Field(
        title="Selected",
        description="Number of selected seismograms in the snapshot",
    )
    flipped_seismogram_count: int = Field(
        title="Flipped",
        description="Number of flipped seismograms in the snapshot",
    )

    cc_mean: float | None = Field(
        default=None,
        title="Stack CC (mean)",
        description="Mean cross-correlation coefficient for this snapshot",
    )

    cc_sem: float | None = Field(
        default=None,
        title="Stack CC (SEM)",
        description="Standard error of the mean of cross-correlation coefficients for this snapshot",
    )

    mccc: bool | None = Field(
        default=None,
        title="MCCC",
        description="Whether MCCC parameters are included in this snapshot",
    )

    event_id: UUID = Field(
        title="Event ID",
        description="ID of the associated event",
        json_schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    short_event_id: str | None = Field(
        title="Short Event ID",
        description="Shortened unique identifier for the associated event",
        json_schema_extra={
            "rich": RichColSpec(
                display_title="Event ID", style="magenta", no_wrap=True, highlight=False
            ),  # type: ignore[dict-item]
        },
    )

    @classmethod
    def from_snapshot(
        cls, snapshot: AimbatSnapshot, session: Session | None = None
    ) -> Self:
        """Create an AimbatSnapshotRead from an AimbatSnapshot ORM instance."""

        short_id = None
        short_event_id = None
        if session is not None:
            from aimbat.utils import uuid_shortener

            short_id = uuid_shortener(session, snapshot)
            short_event_id = uuid_shortener(session, snapshot.event)

        iccs_ccs = [
            q.iccs_cc
            for q in snapshot.seismogram_quality_snapshots
            if q.iccs_cc is not None
        ]
        cc_mean, cc_sem = mean_and_sem(iccs_ccs)
        mccc = bool(snapshot.event_quality_snapshot)

        return cls(
            id=snapshot.id,
            short_id=short_id,
            time=snapshot.time,
            comment=snapshot.comment,
            seismogram_count=snapshot.seismogram_count,
            selected_seismogram_count=snapshot.selected_seismogram_count,
            flipped_seismogram_count=snapshot.flipped_seismogram_count,
            cc_mean=cc_mean,
            cc_sem=cc_sem,
            mccc=mccc,
            event_id=snapshot.event_id,
            short_event_id=short_event_id,
        )


class SnapshotSeismogramResult(BaseModel):
    """Per-seismogram result record from a snapshot.

    Joins the frozen parameter and quality records from a snapshot to produce
    one row per seismogram. Only snapshots with MCCC data will have meaningful
    MCCC columns; `iccs_cc` is populated whenever ICCS was run before the
    snapshot was taken.

    Event- and snapshot-level scalars (`snapshot_id`, `event_id`, `mccc_rmse`)
    are not repeated here — they live in the enclosing `SnapshotResults` envelope.
    """

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    seismogram_id: UUID = Field(
        title="Seismogram ID",
        json_schema_extra={
            "rich": RichColSpec(style="yellow", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    name: str = Field(title="Name", description="Station network and name.")
    channel: str = Field(title="Channel", description="Station channel code.")
    select: bool = Field(
        title="Select",
        description="Whether this seismogram was selected at snapshot time.",
    )
    flip: bool = Field(
        title="Flip",
        description="Whether this seismogram was flipped at snapshot time.",
    )
    t1: PydanticTimestamp | None = Field(
        default=None,
        title="T1",
        description="Frozen pick time (absolute timestamp) at snapshot time.",
    )
    iccs_cc: float | None = Field(
        default=None,
        title="Stack CC",
        description="Cross-correlation coefficient with ICCS stack at snapshot time.",
    )
    mccc_cc_mean: float | None = Field(
        default=None,
        title="MCCC CC",
        description="Mean cross-correlation coefficient of MCCC cluster.",
    )
    mccc_cc_std: float | None = Field(
        default=None,
        title="MCCC CC std",
        description="Standard deviation of cross-correlation coefficients in MCCC cluster.",
    )
    mccc_error: PydanticTimedelta | None = Field(
        default=None,
        title="MCCC err Δt (s)",
        description="Uncertainty in the MCCC arrival time residual in seconds.",
    )

    @classmethod
    def from_snapshot_records(
        cls,
        param_snap: "AimbatSeismogramParametersSnapshot",
        quality_snap: "AimbatSeismogramQualitySnapshot | None",
    ) -> "SnapshotSeismogramResult":
        """Build a result record from pre-loaded snapshot records.

        Warning:
            `param_snap.parameters.seismogram.station` must be loaded before
            calling (e.g. via `selectinload`). `quality_snap.quality` must also
            be loaded when `quality_snap` is not `None`.

        Args:
            param_snap: Seismogram parameters snapshot record.
            quality_snap: Matching seismogram quality snapshot, or `None` if
                no quality data was captured for this seismogram.

        Returns:
            Assembled result record.
        """
        seis = param_snap.parameters.seismogram
        station = seis.station
        name = (f"{station.network}." if station.network else "") + station.name
        return cls(
            seismogram_id=seis.id,
            name=name,
            channel=station.channel,
            select=param_snap.select,
            flip=param_snap.flip,
            t1=param_snap.t1,
            iccs_cc=getattr(quality_snap, "iccs_cc", None),
            mccc_cc_mean=getattr(quality_snap, "mccc_cc_mean", None),
            mccc_cc_std=getattr(quality_snap, "mccc_cc_std", None),
            mccc_error=getattr(quality_snap, "mccc_error", None),
        )


class SnapshotResults(BaseModel):
    """Full results export for a snapshot.

    Contains event- and snapshot-level header information followed by
    per-seismogram result records. All repeated scalars (UUIDs, event
    details, MCCC RMSE) appear once in the envelope rather than being
    duplicated across every row.
    """

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    snapshot_id: UUID = Field(title="Snapshot ID")
    snapshot_time: PydanticTimestamp = Field(title="Snapshot time")
    snapshot_comment: str | None = Field(default=None, title="Snapshot comment")
    event_id: UUID = Field(title="Event ID")
    event_time: PydanticTimestamp = Field(title="Event time")
    event_latitude: float = Field(title="Event latitude")
    event_longitude: float = Field(title="Event longitude")
    event_depth_km: float | None = Field(default=None, title="Event depth (km)")
    mccc_rmse: PydanticTimedelta | None = Field(
        default=None,
        title="MCCC RMSE",
        description="Global MCCC root-mean-square error for the event (seconds).",
    )
    seismograms: list[SnapshotSeismogramResult] = Field(
        title="Seismograms",
        description="Per-seismogram result records.",
    )
