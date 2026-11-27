"""Read models derived from the ORM layer, for display and export.

These models flatten and enrich ORM instances (adding shortened IDs and
aggregated quality statistics) for consumption by the CLI, TUI, and export
commands. They are built via `from_*` classmethods rather than validated
directly from user input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from aimbat.logger import logger
from aimbat.types import PydanticTimedelta, PydanticTimestamp
from aimbat.utils import mean_and_sem, mean_and_sem_timedelta
from aimbat.utils.formatters import (
    fmt_depth_km,
    fmt_flip,
    fmt_float_sem,
    fmt_names,
    fmt_timedelta,
    fmt_timedelta_sem,
    fmt_timestamp,
)

from ._format import RichColSpec, TuiColSpec

if TYPE_CHECKING:
    from pandas import Timestamp
    from sqlmodel import Session

    from aimbat.core._validity import Validity

    from ._models import (
        AimbatEvent,
        AimbatPhase,
        AimbatPick,
        AimbatSeismogram,
        AimbatSeismogramParameters,
        AimbatSeismogramParametersSnapshot,
        AimbatSeismogramQualitySnapshot,
        AimbatSnapshot,
        AimbatStation,
    )

__all__ = [
    "AimbatEventRead",
    "AimbatPhaseRead",
    "AimbatPickRead",
    "AimbatSeismogramRead",
    "AimbatSnapshotRead",
    "AimbatStationRead",
    "SeismogramQualityStats",
    "SnapshotResults",
    "SnapshotSeismogramResult",
]


def _row_for(
    seismogram: AimbatSeismogram,
    phase_name: str | None,
    phase_id: UUID | None = None,
) -> AimbatSeismogramParameters | None:
    """The seismogram's row for the given phase, or its only row without one.

    `None` if there is no such row, or no phase is given and the seismogram
    has several.
    """
    rows = seismogram.phase_rows
    if phase_id is not None:
        return next((row for row in rows if row.phase_id == phase_id), None)
    if phase_name is None:
        return rows[0] if len(rows) == 1 else None
    return next((row for row in rows if row.phase.name == phase_name), None)


class SeismogramQualityStats(BaseModel):
    """Aggregated seismogram quality statistics for a phase or station.

    Built from persisted `AimbatSeismogramQuality` rows, covering both ICCS
    CC and MCCC diagnostics. All mean fields are `None` when no seismograms
    in the group have quality data. SEM fields are `None` when fewer than
    two values are available. `mccc_rmse` and the event and phase fields are
    populated by `from_phase` and `from_snapshot`, and are always `None` for
    `from_station`, which aggregates over every phase.

    For the live, DB-independent CC-only equivalent (computed straight from
    an `ICCS` instance), see `aimbat.core.CcStats`.
    """

    model_config = ConfigDict(frozen=True)

    event_id: UUID | None = Field(
        default=None,
        title="Event ID",
        json_schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    phase_id: UUID | None = Field(
        default=None,
        title="Phase ID",
        json_schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    phase_name: str | None = Field(default=None, title="Phase")
    phase_component: str | None = Field(default=None, title="Component")
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
    count: int = Field(
        title="Count",
        description=(
            "Number of seismograms in the group (regardless of whether they"
            + " have quality data). `from_phase`/`from_station` count live"
            + " seismograms directly; `from_snapshot` uses the snapshot's own"
            + " seismogram-parameter-snapshot count instead. The mean/SEM"
            + " fields above only aggregate the subset that has quality data,"
            + " which may be smaller than this count."
        ),
    )
    cc_mean: float | None = Field(default=None, title="ICCS CC mean")
    cc_mean_sem: float | None = Field(default=None, title="ICCS CC mean SEM")
    mccc_cc_mean: float | None = Field(default=None, title="MCCC CC mean")
    mccc_cc_mean_sem: float | None = Field(default=None, title="MCCC CC mean SEM")
    mccc_cc_std: float | None = Field(default=None, title="MCCC CC std")
    mccc_cc_std_sem: float | None = Field(default=None, title="MCCC CC std SEM")
    mccc_error: PydanticTimedelta | None = Field(default=None, title="MCCC err Δt (s)")
    mccc_error_sem: PydanticTimedelta | None = Field(
        default=None, title="MCCC err Δt SEM (s)"
    )
    mccc_rmse: PydanticTimedelta | None = Field(default=None, title="MCCC RMSE (s)")

    @property
    def cc_display(self) -> str:
        """ICCS CC mean ± SEM, formatted for display."""
        return fmt_float_sem(self.cc_mean, self.cc_mean_sem)

    @property
    def mccc_cc_mean_display(self) -> str:
        """MCCC CC mean ± SEM, formatted for display."""
        return fmt_float_sem(self.mccc_cc_mean, self.mccc_cc_mean_sem)

    @property
    def mccc_cc_std_display(self) -> str:
        """MCCC CC std ± SEM, formatted for display."""
        return fmt_float_sem(self.mccc_cc_std, self.mccc_cc_std_sem)

    @property
    def mccc_error_display(self) -> str:
        """MCCC arrival-time error mean ± SEM in seconds, formatted for display."""
        return fmt_timedelta_sem(self.mccc_error, self.mccc_error_sem)

    @property
    def mccc_rmse_display(self) -> str:
        """MCCC RMSE in seconds, formatted for display."""
        return fmt_timedelta(self.mccc_rmse)

    @classmethod
    def from_phase(cls, phase: AimbatPhase, validity: Validity) -> Self:
        """Build quality stats from live quality records for a phase.

        Aggregates `iccs_cc` and MCCC metrics across the seismograms of the
        phase that have valid live quality values. `mccc_rmse` is taken from
        the phase quality record.

        Warning:
            This method may trigger lazy-loading of the phase's rows, their
            quality and the phase quality. For performance, query `phase`
            with `selectinload` for these relationships before calling.

        Args:
            phase: The phase whose seismograms' live quality to aggregate.
            validity: Validity covering the phase.

        Returns:
            Aggregated quality statistics.
        """
        logger.debug(f"Building quality stats for phase {phase.id}.")
        rows = phase.seismogram_parameters
        mccc_qualities = [
            row.quality
            for row in rows
            if row.quality is not None and validity.mccc(phase.id)
        ]

        cc_mean, cc_mean_sem = mean_and_sem(
            [
                row.quality.iccs_cc
                for row in rows
                if row.quality is not None
                and row.quality.iccs_cc is not None
                and validity.iccs_cc(row.id)
            ]
        )
        mccc_cc_mean, mccc_cc_mean_sem = mean_and_sem(
            [q.mccc_cc_mean for q in mccc_qualities if q.mccc_cc_mean is not None]
        )
        mccc_cc_std, mccc_cc_std_sem = mean_and_sem(
            [q.mccc_cc_std for q in mccc_qualities if q.mccc_cc_std is not None]
        )
        mccc_error, mccc_error_sem = mean_and_sem_timedelta(
            [q.mccc_error for q in mccc_qualities if q.mccc_error is not None]
        )
        mccc_rmse = (
            phase.quality.mccc_rmse
            if phase.quality is not None and validity.mccc(phase.id)
            else None
        )

        return cls(
            event_id=phase.event_id,
            phase_id=phase.id,
            phase_name=phase.name,
            phase_component=phase.component,
            count=len(rows),
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
    def from_station(cls, station: AimbatStation, validity: Validity) -> Self:
        """Build quality stats from live quality records for a station.

        Aggregates `iccs_cc` and MCCC metrics across all seismograms at the
        station that have valid live quality values.

        Warning:
            This method may trigger lazy-loading of `station.seismograms` and
            their rows and quality. For performance, query `station` with
            `selectinload` for these relationships before calling.

        Args:
            station: The station whose seismograms' live quality to aggregate.
            validity: Validity covering every event the station recorded.

        Returns:
            Aggregated quality statistics. `mccc_rmse` is always `None`.
        """
        logger.debug(f"Building quality stats for station {station.id}.")
        rows = [row for seis in station.seismograms for row in seis.phase_rows]
        iccs_ccs = [
            row.quality.iccs_cc
            for row in rows
            if row.quality is not None
            and row.quality.iccs_cc is not None
            and validity.iccs_cc(row.id)
        ]
        mccc_qualities = [
            row.quality
            for row in rows
            if row.quality is not None and validity.mccc(row.phase_id)
        ]

        cc_mean, cc_mean_sem = mean_and_sem(iccs_ccs)
        mccc_cc_mean, mccc_cc_mean_sem = mean_and_sem(
            [q.mccc_cc_mean for q in mccc_qualities if q.mccc_cc_mean is not None]
        )
        mccc_cc_std, mccc_cc_std_sem = mean_and_sem(
            [q.mccc_cc_std for q in mccc_qualities if q.mccc_cc_std is not None]
        )
        mccc_error, mccc_error_sem = mean_and_sem_timedelta(
            [q.mccc_error for q in mccc_qualities if q.mccc_error is not None]
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
        eq = snapshot.phase_quality_snapshot
        mccc_rmse = eq.mccc_rmse if eq is not None else None

        return cls(
            event_id=snapshot.phase.event_id,
            phase_id=snapshot.phase_id,
            phase_name=snapshot.phase.name,
            phase_component=snapshot.phase.component,
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
        json_schema_extra={
            "tui": TuiColSpec(formatter=fmt_timestamp),  # type: ignore[dict-item]
            "rich": RichColSpec(formatter=fmt_timestamp),  # type: ignore[dict-item]
        },
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
    phases: list[str] = Field(
        title="Phases",
        description="Names of the event's phases, sorted",
        json_schema_extra={
            "tui": TuiColSpec(formatter=fmt_names),  # type: ignore[dict-item]
            "rich": RichColSpec(formatter=fmt_names),  # type: ignore[dict-item]
        },
    )
    seismogram_count: int = Field(
        title="Seismograms",
        description="Number of seismograms associated with this event",
    )
    site_count: int = Field(
        title="Sites",
        description=(
            "Number of sites (network and station code) with seismograms for "
            + "this event"
        ),
    )
    snapshot_count: int = Field(
        title="Snapshots",
        description="Number of snapshots of the event's phases",
    )

    @classmethod
    def from_event(cls, event: AimbatEvent, session: Session | None = None) -> Self:
        """Create an AimbatEventRead from an AimbatEvent ORM instance."""
        data = event.model_dump()

        if session is not None:
            from aimbat.utils import uuid_shortener

            data["short_id"] = uuid_shortener(session, event)

        data.update(
            {
                "completed": bool(event.phases)
                and all(phase.parameters.completed for phase in event.phases),
                "phases": sorted(phase.name for phase in event.phases),
                "seismogram_count": event.seismogram_count or 0,
                "site_count": event.site_count or 0,
                "snapshot_count": event.snapshot_count or 0,
            }
        )
        return cls(**data)


class AimbatPhaseRead(BaseModel):
    """Read model for AimbatPhase with its counts and processing state."""

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: UUID = Field(
        title="ID",
        description="Unique identifier for the phase",
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
    name: str = Field(title="Phase", description="Name of the phase")
    component: str = Field(
        default="",
        title="Component",
        description="Component of the phase, empty when its channels have none",
    )
    event_time: PydanticTimestamp = Field(
        title="Event time",
        description="Origin time of the phase's event",
        json_schema_extra={
            "tui": TuiColSpec(formatter=fmt_timestamp),  # type: ignore[dict-item]
            "rich": RichColSpec(formatter=fmt_timestamp),  # type: ignore[dict-item]
        },
    )
    completed: bool = Field(
        title="Completed",
        description="Whether the phase is marked as completed",
        json_schema_extra={"tui": TuiColSpec(text_align="center")},  # type: ignore[dict-item]
    )
    seismogram_count: int = Field(
        title="Seismograms",
        description="Number of seismograms in the phase",
    )
    selected_seismogram_count: int = Field(
        title="Selected",
        description="Number of selected seismograms in the phase",
    )
    mccc: bool = Field(
        title="MCCC",
        description="Whether the phase has MCCC results valid for its current parameters",
    )
    snapshot_count: int = Field(
        title="Snapshots",
        description="Number of snapshots of the phase",
    )
    event_id: UUID = Field(
        title="Event ID",
        description="ID of the phase's event",
        json_schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    short_event_id: str | None = Field(
        default=None,
        title="Short Event ID",
        description="Shortened unique identifier for the phase's event",
        json_schema_extra={
            "rich": RichColSpec(
                display_title="Event ID", style="magenta", no_wrap=True, highlight=False
            ),  # type: ignore[dict-item]
        },
    )

    @classmethod
    def from_phase(
        cls, phase: AimbatPhase, validity: Validity, session: Session | None = None
    ) -> Self:
        """Create an AimbatPhaseRead from an AimbatPhase ORM instance.

        Warning:
            This method may trigger lazy-loading of the phase's event,
            parameters, quality and rows. For performance, query `phase`
            with `selectinload` for these relationships before calling.

        Args:
            phase: The phase.
            validity: Validity covering the phase.
            session: Session for the short IDs.
        """
        short_id = None
        short_event_id = None
        if session is not None:
            from aimbat.utils import uuid_shortener

            short_id = uuid_shortener(session, phase)
            short_event_id = uuid_shortener(session, phase.event)

        rows = phase.seismogram_parameters
        return cls(
            id=phase.id,
            short_id=short_id,
            name=phase.name,
            component=phase.component,
            event_time=phase.event.time,
            completed=phase.parameters.completed,
            seismogram_count=len(rows),
            selected_seismogram_count=sum(row.select for row in rows),
            mccc=phase.quality is not None and validity.mccc(phase.id),
            snapshot_count=phase.snapshot_count or 0,
            event_id=phase.event_id,
            short_event_id=short_event_id,
        )


def _fmt_pick_time(val: object) -> str:
    """Format a pick time to the millisecond."""
    from pandas import Timestamp

    if isinstance(val, str):
        val = Timestamp(val)
    if isinstance(val, Timestamp):
        return val.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return str(val)


def _describe_target(pick: AimbatPick) -> str | None:
    """The target a pick was read with, as text."""
    if pick.target_seismogram_id is not None:
        return f"seismogram {pick.target_seismogram_id}"
    codes = (
        pick.target_network,
        pick.target_station,
        pick.target_location,
        pick.target_channel,
    )
    if all(code is None for code in codes) and pick.target_event_time is None:
        return None
    text = ".".join("*" if code is None else code for code in codes)
    if pick.target_event_time is not None:
        text += f" {fmt_timestamp(pick.target_event_time)}"
    return text


class AimbatPickRead(BaseModel):
    """Read model for AimbatPick with its derived state."""

    model_config = ConfigDict(
        frozen=True, alias_generator=to_camel, populate_by_name=True
    )

    id: UUID = Field(
        title="ID",
        description="Unique identifier for the pick",
        json_schema_extra={
            "rich": RichColSpec(style="yellow", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    short_id: str | None = Field(
        default=None,
        title="Short ID",
        description="Shortened unique identifier",
        json_schema_extra={
            "rich": RichColSpec(
                display_title="ID", style="yellow", no_wrap=True, highlight=False
            ),  # type: ignore[dict-item]
        },
    )
    event_time: PydanticTimestamp | None = Field(
        default=None,
        title="Event time",
        description="Origin time of the pick's event, if known",
        json_schema_extra={
            "rich": RichColSpec(formatter=fmt_timestamp),  # type: ignore[dict-item]
        },
    )
    time: PydanticTimestamp = Field(
        title="Time",
        description="Pick time",
        json_schema_extra={
            "rich": RichColSpec(formatter=_fmt_pick_time),  # type: ignore[dict-item]
        },
    )
    label: str | None = Field(
        default=None, title="Label", description="Label the pick was read with"
    )
    phase_name: str | None = Field(
        default=None, title="Phase", description="Phase name of the pick"
    )
    state: str = Field(title="State", description="Derived state of the pick")
    seismogram_id: UUID | None = Field(
        default=None,
        title="Seismogram ID",
        description="ID of the seismogram the pick is matched to",
        json_schema_extra={
            "rich": RichColSpec(style="magenta", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    short_seismogram_id: str | None = Field(
        default=None,
        title="Short Seismogram ID",
        description="Shortened ID of the seismogram the pick is matched to",
        json_schema_extra={
            "rich": RichColSpec(
                display_title="Seismogram",
                style="magenta",
                no_wrap=True,
                highlight=False,
            ),  # type: ignore[dict-item]
        },
    )
    target: str | None = Field(
        default=None,
        title="Target",
        description="Target the pick was read with",
    )
    source_name: str | None = Field(
        default=None,
        title="Source",
        description="Name of the source the pick was read from",
    )
    source_key: str | None = Field(
        default=None,
        title="Key",
        description="Key identifying the pick within its source",
    )

    @classmethod
    def from_pick(
        cls,
        pick: AimbatPick,
        state: str,
        event_time: Timestamp | None,
        session: Session | None = None,
    ) -> Self:
        """Create an AimbatPickRead from an AimbatPick ORM instance.

        Args:
            pick: The pick.
            state: Derived state of the pick.
            event_time: Origin time of the pick's event, if known.
            session: Session for the short IDs.
        """
        short_id = None
        short_seismogram_id = None
        if session is not None:
            from aimbat.utils import uuid_shortener

            from ._models import AimbatSeismogram

            short_id = uuid_shortener(session, pick)
            if pick.seismogram_id is not None:
                short_seismogram_id = uuid_shortener(
                    session, AimbatSeismogram, str_uuid=str(pick.seismogram_id)
                )
        return cls(
            id=pick.id,
            short_id=short_id,
            event_time=event_time,
            time=pick.time,
            label=pick.label,
            phase_name=pick.phase_name,
            state=state,
            seismogram_id=pick.seismogram_id,
            short_seismogram_id=short_seismogram_id,
            target=_describe_target(pick),
            source_name=pick.source_name,
            source_key=pick.source_key,
        )


class AimbatStationRead(BaseModel):
    """Read model for AimbatStation including aggregated quality statistics."""

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
    location: str = Field(title="Location", description="Station location code")
    channel: str = Field(title="Channel", description="Station channel code")
    component: str | None = Field(
        default=None,
        title="Component",
        description="Component letter of the channel code",
    )
    latitude: float = Field(title="Latitude", description="Station latitude")
    longitude: float = Field(title="Longitude", description="Station longitude")
    elevation: float | None = Field(
        default=None,
        title="Elevation",
        description="Station elevation",
        json_schema_extra={
            "tui": TuiColSpec(formatter=lambda x: str(int(x))),  # type: ignore[dict-item]
            "rich": RichColSpec(formatter=lambda x: str(int(x))),  # type: ignore[dict-item]
        },
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
        validity: Validity,
        session: Session | None = None,
    ) -> Self:
        """Create an AimbatStationRead from an AimbatStation ORM instance.

        Args:
            station: The station.
            validity: Validity covering every event the station recorded.
            session: Session for the short ID and the CC statistics.
        """
        data = station.model_dump()
        data["component"] = station.component

        if session is not None:
            from aimbat.utils import uuid_shortener

            data["short_id"] = uuid_shortener(session, station)
            iccs_ccs = tuple(
                row.quality.iccs_cc
                for seis in station.seismograms
                for row in seis.phase_rows
                if row.quality is not None
                and row.quality.iccs_cc is not None
                and validity.iccs_cc(row.id)
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

    location: str = Field(title="Location", description="Station location code.")

    channel: str = Field(
        title="Channel",
        description="Seismogram channel.",
    )

    component: str | None = Field(
        default=None,
        title="Component",
        description="Component letter of the channel code.",
    )

    select: bool | None = Field(
        title="Select",
        description="Whether the seismogram is selected for processing.",
        json_schema_extra={"tui": TuiColSpec(text_align="center")},  # type: ignore[dict-item]
    )

    flip: bool | None = Field(
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
        cls,
        seismogram: AimbatSeismogram,
        validity: Validity,
        session: Session | None = None,
        phase_name: str | None = None,
        phase_id: UUID | None = None,
    ) -> Self:
        """Create an AimbatSeismogramRead from an AimbatSeismogram ORM instance.

        The processing columns (`select`, `flip`, picks and quality) come
        from the seismogram's row for the given phase, or from its only row
        when no phase is given. They are empty when there is no such row.

        Args:
            seismogram: The seismogram.
            validity: Validity covering the phases of the seismogram's event.
            session: Session for the short IDs.
            phase_name: Name of the phase whose processing state is shown.
            phase_id: ID of the phase whose processing state is shown, taking
                precedence over `phase_name`.
        """
        name = (
            f"{seismogram.station.network}." if seismogram.station.network else ""
        ) + seismogram.station.name

        short_id = None
        short_event_id = None
        if session is not None:
            from aimbat.utils import uuid_shortener

            short_id = uuid_shortener(session, seismogram)
            short_event_id = uuid_shortener(session, seismogram.event)

        row = _row_for(seismogram, phase_name, phase_id)
        delta_t = (
            row.refined_pick - row.initial_pick
            if row is not None and row.refined_pick
            else None
        )
        quality = row.quality if row is not None else None
        iccs_quality = quality if row is not None and validity.iccs_cc(row.id) else None
        mccc_quality = (
            quality if row is not None and validity.mccc(row.phase_id) else None
        )
        return cls(
            id=seismogram.id,
            short_id=short_id,
            name=name,
            location=seismogram.station.location,
            channel=seismogram.station.channel,
            component=seismogram.station.component,
            select=row.select if row is not None else None,
            flip=row.flip if row is not None else None,
            delta_t=delta_t,
            mccc_error=mccc_quality.mccc_error if mccc_quality else None,
            iccs_cc=iccs_quality.iccs_cc if iccs_quality else None,
            mccc_cc_mean=mccc_quality.mccc_cc_mean if mccc_quality else None,
            mccc_cc_std=mccc_quality.mccc_cc_std if mccc_quality else None,
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

    phase_name: str = Field(
        title="Phase",
        description="Name of the phase the snapshot was taken of",
    )

    phase_component: str = Field(
        default="",
        title="Component",
        description="Component of the phase the snapshot was taken of",
    )

    sequence: int = Field(
        title="Seq",
        description="Monotonic per-phase snapshot counter",
    )

    automatic: bool = Field(
        title="Auto", description="Whether this snapshot was created automatically"
    )

    time: PydanticTimestamp = Field(
        title="Time",
        description="Timestamp of the snapshot",
        json_schema_extra={
            "tui": TuiColSpec(formatter=fmt_timestamp),  # type: ignore[dict-item]
            "rich": RichColSpec(formatter=fmt_timestamp),  # type: ignore[dict-item]
        },
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
            short_event_id = uuid_shortener(session, snapshot.phase.event)

        iccs_ccs = [
            q.iccs_cc
            for q in snapshot.seismogram_quality_snapshots
            if q.iccs_cc is not None
        ]
        cc_mean, cc_sem = mean_and_sem(iccs_ccs)
        mccc = bool(snapshot.phase_quality_snapshot)

        return cls(
            id=snapshot.id,
            short_id=short_id,
            phase_name=snapshot.phase.name,
            phase_component=snapshot.phase.component,
            sequence=snapshot.sequence,
            time=snapshot.time,
            comment=snapshot.comment,
            automatic=snapshot.automatic,
            seismogram_count=snapshot.seismogram_count,
            selected_seismogram_count=snapshot.selected_seismogram_count,
            flipped_seismogram_count=snapshot.flipped_seismogram_count,
            cc_mean=cc_mean,
            cc_sem=cc_sem,
            mccc=mccc,
            event_id=snapshot.phase.event_id,
            short_event_id=short_event_id,
        )


class SnapshotSeismogramResult(BaseModel):
    """Per-seismogram result record from a snapshot.

    Joins the frozen parameter and quality records from a snapshot to produce
    one row per seismogram. Only snapshots with MCCC data will have meaningful
    MCCC columns; `iccs_cc` is populated whenever ICCS was run before the
    snapshot was taken.

    Event- and snapshot-level scalars (`snapshot_id`, `event_id`, `mccc_rmse`)
    are not repeated here; they live in the enclosing `SnapshotResults` envelope.
    """

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    seismogram_id: UUID | None = Field(
        default=None,
        title="Seismogram ID",
        json_schema_extra={
            "rich": RichColSpec(style="yellow", no_wrap=True, highlight=False),  # type: ignore[dict-item]
        },
    )
    name: str = Field(title="Name", description="Station network and name.")
    location: str = Field(title="Location", description="Station location code.")
    channel: str = Field(title="Channel", description="Station channel code.")
    component: str | None = Field(
        default=None,
        title="Component",
        description="Component letter of the channel code.",
    )
    select: bool = Field(
        title="Select",
        description="Whether this seismogram was selected at snapshot time.",
    )
    flip: bool = Field(
        title="Flip",
        description="Whether this seismogram was flipped at snapshot time.",
    )
    refined_pick: PydanticTimestamp | None = Field(
        default=None,
        title="Refined pick",
        description="Refined pick (absolute timestamp) at snapshot time.",
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
        param_snap: AimbatSeismogramParametersSnapshot,
        quality_snap: AimbatSeismogramQualitySnapshot | None,
        live_seismogram: AimbatSeismogram | None,
    ) -> SnapshotSeismogramResult:
        """Build a result record from pre-loaded snapshot records.

        Warning:
            `live_seismogram.station` must be loaded before calling (e.g. via
            `selectinload`) when `live_seismogram` is not `None`.

        Args:
            param_snap: Seismogram parameters snapshot record.
            quality_snap: Matching seismogram quality snapshot, or `None` if
                no quality data were captured for this seismogram.
            live_seismogram: The live seismogram the snapshot was taken from,
                or `None` if it has since been deleted.

        Returns:
            Assembled result record.
        """
        from ._models import channel_component

        if live_seismogram is not None:
            station = live_seismogram.station
            name = (f"{station.network}." if station.network else "") + station.name
            location = station.location
            channel = station.channel
        else:
            name = "(deleted)"
            location = ""
            channel = ""
        return cls(
            seismogram_id=param_snap.seismogram_id,
            name=name,
            location=location,
            channel=channel,
            component=channel_component(channel),
            select=param_snap.select,
            flip=param_snap.flip,
            refined_pick=param_snap.refined_pick,
            iccs_cc=quality_snap.iccs_cc if quality_snap else None,
            mccc_cc_mean=quality_snap.mccc_cc_mean if quality_snap else None,
            mccc_cc_std=quality_snap.mccc_cc_std if quality_snap else None,
            mccc_error=quality_snap.mccc_error if quality_snap else None,
        )


class SnapshotResults(BaseModel):
    """Full results export for a snapshot.

    Contains event- and snapshot-level header information followed by
    per-seismogram result records. All repeated scalars (UUIDs, event
    details, MCCC RMSE) appear once in the envelope rather than being
    duplicated across every row.

    Depth is exposed in metres, matching the database column.
    """

    model_config = ConfigDict(
        frozen=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    snapshot_id: UUID = Field(title="Snapshot ID")
    snapshot_time: PydanticTimestamp = Field(title="Snapshot time")
    snapshot_comment: str | None = Field(default=None, title="Snapshot comment")
    phase_id: UUID = Field(title="Phase ID")
    phase_name: str = Field(title="Phase")
    phase_component: str = Field(default="", title="Component")
    event_id: UUID = Field(title="Event ID")
    event_time: PydanticTimestamp = Field(title="Event time")
    event_latitude: float = Field(title="Event latitude")
    event_longitude: float = Field(title="Event longitude")
    event_depth: float | None = Field(
        default=None,
        title="Event depth (m)",
        description="Event depth in metres.",
    )
    mccc_rmse: PydanticTimedelta | None = Field(
        default=None,
        title="MCCC RMSE (s)",
        description="Global MCCC root-mean-square error for the event.",
    )
    seismograms: list[SnapshotSeismogramResult] = Field(
        title="Seismograms",
        description="Per-seismogram result records.",
    )
