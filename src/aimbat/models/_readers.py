from typing import TYPE_CHECKING, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from aimbat._types import PydanticTimedelta, PydanticTimestamp
from aimbat.utils import mean_and_sem
from aimbat.utils.formatters import fmt_depth_km, fmt_flip

from ._format import RichColSpec, TuiColSpec

if TYPE_CHECKING:
    from sqlmodel import Session

    from ._models import AimbatEvent, AimbatSeismogram, AimbatSnapshot, AimbatStation

__all__ = [
    "AimbatEventRead",
    "AimbatSeismogramRead",
    "AimbatSnapshotRead",
    "AimbatStationRead",
]


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
        station: "AimbatStation",
        session: "Session | None" = None,
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
        cls, seismogram: "AimbatSeismogram", session: "Session | None" = None
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
        cls, snapshot: "AimbatSnapshot", session: "Session | None" = None
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
