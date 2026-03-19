"""Display views and quality metrics for AIMBAT.

Provides two layers:

- **Raw quality data** — `SeismogramQualityStats`, `get_quality_*`,
  `dump_quality_*`: SQL retrieval, aggregation, and JSON-serialisable export.
- **Structured view data** — `FieldSpec`, `FieldGroup`, and
  `*_quality_groups` functions: ready-to-render lists of labelled field values
  consumed by the TUI, GUI, and CLI display layers.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from aimbat._types import PydanticTimedelta
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatEventQualityBase,
    AimbatEventQualitySnapshot,
    AimbatSeismogram,
    AimbatSeismogramParametersSnapshot,
    AimbatSeismogramQualityBase,
    AimbatSeismogramQualitySnapshot,
    AimbatSnapshot,
)
from aimbat.utils import mean_and_sem, mean_and_sem_timedelta, rel

__all__ = [
    "FieldSpec",
    "FieldGroup",
    "SeismogramQualityStats",
    "get_quality_seismogram",
    "get_quality_event",
    "get_quality_station",
    "dump_quality_event",
    "dump_quality_station",
    "get_seismogram_mccc_map",
    "seismogram_quality_groups",
    "event_quality_groups",
    "station_quality_groups",
    "snapshot_quality_groups",
]


# ---------------------------------------------------------------------------
# View data structures
# ---------------------------------------------------------------------------


@dataclass
class FieldSpec:
    """A single labelled field value for display.

    The `name` is the canonical key used in JSON and enum lookups.
    The `title` is the human-readable label sourced from the model's
    `Field(title=...)`. `value` and `sem` are raw Python values;
    formatters live in the rendering layer.
    """

    name: str
    title: str
    value: Any
    sem: Any = None


@dataclass
class FieldGroup:
    """A labelled group of `FieldSpec` instances for display.

    When `fields` is empty the rendering layer should show
    `empty_message` if provided.
    """

    title: str
    fields: list[FieldSpec] = field(default_factory=list)
    empty_message: str | None = None


# ---------------------------------------------------------------------------
# Aggregated seismogram quality stats (Pydantic model)
# ---------------------------------------------------------------------------


class SeismogramQualityStats(BaseModel):
    """Aggregated seismogram quality statistics computed from one or more seismograms.

    All mean fields are None when no seismograms in the group have quality data.
    SEM fields are None when fewer than two values are available.
    """

    model_config = ConfigDict(frozen=True)

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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _stats_from_quality_snapshots(
    records: list[AimbatSeismogramQualitySnapshot],
) -> SeismogramQualityStats:
    """Aggregate seismogram quality snapshot records into a `SeismogramQualityStats`."""
    iccs_cc_vals = [r.iccs_cc for r in records if r.iccs_cc is not None]
    mccc_cc_mean_vals = [r.mccc_cc_mean for r in records if r.mccc_cc_mean is not None]
    mccc_cc_std_vals = [r.mccc_cc_std for r in records if r.mccc_cc_std is not None]
    mccc_error_vals = [r.mccc_error for r in records if r.mccc_error is not None]

    cc_mean, cc_mean_sem = mean_and_sem(iccs_cc_vals)
    mccc_cc_mean, mccc_cc_mean_sem = mean_and_sem(mccc_cc_mean_vals)
    cc_std_mean, cc_std_sem = mean_and_sem(mccc_cc_std_vals)
    error_mean, error_sem = mean_and_sem_timedelta(mccc_error_vals)

    return SeismogramQualityStats(
        count=len(records),
        cc_mean=cc_mean,
        cc_mean_sem=cc_mean_sem,
        mccc_cc_mean=mccc_cc_mean,
        mccc_cc_mean_sem=mccc_cc_mean_sem,
        mccc_cc_std=cc_std_mean,
        mccc_cc_std_sem=cc_std_sem,
        mccc_error=error_mean,
        mccc_error_sem=error_sem,
    )


def _stats_dump(stats: SeismogramQualityStats, prefix: str = "") -> dict[str, Any]:
    """Serialise SeismogramQualityStats to a flat JSON-serialisable dict.

    Timedelta values are serialised as total seconds (float) via PydanticTimedelta.
    An optional prefix is prepended to every key.
    """
    raw = stats.model_dump(mode="json")
    if not prefix:
        return raw
    return {f"{prefix}{k}": v for k, v in raw.items()}


def _specs_from_model(
    obj: BaseModel,
    fields_from: type[BaseModel],
) -> list[FieldSpec]:
    """Build a `FieldSpec` list from a model instance.

    Iterates `fields_from.model_fields` so that id and foreign-key columns
    added by table subclasses are excluded. Fields whose names end in `_sem`
    are treated as SEM companions and paired with their parent field.
    """
    fields = fields_from.model_fields
    specs = []
    for name, field_info in fields.items():
        if name.endswith("_sem"):
            continue
        val = getattr(obj, name)
        sem_name = f"{name}_sem"
        sem = getattr(obj, sem_name, None) if sem_name in fields else None
        specs.append(
            FieldSpec(
                name=name,
                title=field_info.title or name,
                value=val,
                sem=sem,
            )
        )
    return specs


def _latest_snapshot_seis_quality(
    session: Session, event_id: uuid.UUID
) -> list[AimbatSeismogramQualitySnapshot]:
    """Return seismogram quality records from the most recent snapshot with MCCC data."""
    stmt = (
        select(AimbatSnapshot)
        .join(
            AimbatEventQualitySnapshot,
            col(AimbatEventQualitySnapshot.snapshot_id) == col(AimbatSnapshot.id),
        )
        .where(col(AimbatSnapshot.event_id) == event_id)
        .order_by(col(AimbatSnapshot.time).desc())
        .limit(1)
    )
    snapshot = session.exec(stmt).first()
    if snapshot is None:
        return []
    return snapshot.seismogram_quality_snapshots


# ---------------------------------------------------------------------------
# Per-seismogram MCCC display map
# ---------------------------------------------------------------------------


def get_seismogram_mccc_map(
    event: AimbatEvent,
) -> dict[uuid.UUID, tuple[pd.Timedelta | None, float, float | None]]:
    """Return per-seismogram MCCC quality values for display from the live quality table.

    Reads directly from the `AimbatSeismogramQuality` live records for the
    event's seismograms. Only seismograms with a non-None `mccc_cc_mean` are
    included (i.e. those for which MCCC has been run).

    Must be called within an active SQLModel session so that ORM relationships
    on `event` can lazy-load.

    Warning:
        This function can cause an N+1 query issue. It iterates over
        `event.seismograms` and accesses `seis.quality`, which may trigger
        lazy loading. To avoid performance problems, the `AimbatEvent` object
        passed to this function should be queried with `selectinload` for the
        `seismograms` and their nested `quality` relationships.

    Args:
        event: Default AimbatEvent.

    Returns:
        Mapping from seismogram ID to `(mccc_error, mccc_cc_mean, mccc_cc_std)`.
        Empty when MCCC has not been run.
    """
    result: dict[uuid.UUID, tuple[pd.Timedelta | None, float, float | None]] = {}
    for seis in event.seismograms:
        sq = seis.quality
        if sq is not None and sq.mccc_cc_mean is not None:
            result[seis.id] = (sq.mccc_error, sq.mccc_cc_mean, sq.mccc_cc_std)
    return result


# ---------------------------------------------------------------------------
# Raw quality retrieval
# ---------------------------------------------------------------------------


def get_quality_seismogram(
    session: Session, seismogram_id: uuid.UUID
) -> AimbatSeismogramQualitySnapshot | None:
    """Get the quality snapshot for a seismogram from the most recent MCCC run.

    Returns the seismogram's quality record from the most recent snapshot that
    has event-level quality data. Returns None if no MCCC has been run, if
    the seismogram has no live quality record, or if the most recent MCCC run
    excluded this seismogram.

    Args:
        session: Database session.
        seismogram_id: Seismogram UUID.

    Returns:
        The `AimbatSeismogramQualitySnapshot` from the most recent MCCC snapshot
        that includes this seismogram, or None.
    """
    logger.debug(f"Getting quality for seismogram {seismogram_id}.")

    seismogram = session.get(AimbatSeismogram, seismogram_id)
    if seismogram is None:
        return None
    if seismogram.quality is None:
        return None
    quality_id = seismogram.quality.id

    snap_stmt = (
        select(AimbatSnapshot)
        .join(
            AimbatEventQualitySnapshot,
            col(AimbatEventQualitySnapshot.snapshot_id) == col(AimbatSnapshot.id),
        )
        .where(col(AimbatSnapshot.event_id) == seismogram.event_id)
        .order_by(col(AimbatSnapshot.time).desc())
        .limit(1)
    )
    latest = session.exec(snap_stmt).first()
    if latest is None:
        return None

    stmt = select(AimbatSeismogramQualitySnapshot).where(
        col(AimbatSeismogramQualitySnapshot.snapshot_id) == latest.id,
        col(AimbatSeismogramQualitySnapshot.seismogram_quality_id) == quality_id,
    )
    return session.exec(stmt).first()


def get_quality_event(
    session: Session, event_id: uuid.UUID
) -> tuple[AimbatEventQualitySnapshot | None, SeismogramQualityStats]:
    """Get MCCC quality metrics for an event from the most recent snapshot.

    Returns the event-level quality record together with aggregated seismogram
    quality statistics across all seismograms included in that MCCC run.

    Args:
        session: Database session.
        event_id: Event UUID.

    Returns:
        A tuple of `(event_quality_snapshot, stats)`.
        `event_quality_snapshot` is None if no MCCC has been run yet.
    """
    logger.debug(f"Getting quality for event {event_id}.")

    stmt = (
        select(AimbatSnapshot)
        .join(
            AimbatEventQualitySnapshot,
            col(AimbatEventQualitySnapshot.snapshot_id) == col(AimbatSnapshot.id),
        )
        .where(col(AimbatSnapshot.event_id) == event_id)
        .order_by(col(AimbatSnapshot.time).desc())
        .limit(1)
    )
    latest = session.exec(stmt).first()

    if latest is None:
        return None, SeismogramQualityStats(count=0)

    event_quality = latest.event_quality_snapshot
    stats = _stats_from_quality_snapshots(latest.seismogram_quality_snapshots)
    return event_quality, stats


def get_quality_station(
    session: Session, station_id: uuid.UUID
) -> tuple[SeismogramQualityStats, SeismogramQualityStats]:
    """Get aggregated MCCC quality metrics for a station from the most recent snapshots.

    Args:
        session: Database session.
        station_id: Station UUID.

    Returns:
        A tuple of `(all_stats, selected_stats)`.
    """
    logger.debug(f"Getting quality for station {station_id}.")

    # 1. Get all event IDs for the station
    stmt = (
        select(AimbatSeismogram.event_id)
        .where(col(AimbatSeismogram.station_id) == station_id)
        .distinct()
    )
    event_ids = session.exec(stmt).all()

    if not event_ids:
        return SeismogramQualityStats(count=0), SeismogramQualityStats(count=0)

    # 2. Get the latest snapshot for each of these events that has quality data.
    # Using a subquery to get the max time for each event_id
    subq = (
        select(
            AimbatSnapshot.event_id,
            func.max(AimbatSnapshot.time).label("max_time"),
        )
        .join(AimbatEventQualitySnapshot)
        .where(col(AimbatSnapshot.event_id).in_(event_ids))
        .group_by(col(AimbatSnapshot.event_id))
        .subquery()
    )

    # Now join the snapshot table with the subquery to get the latest snapshots
    snap_stmt = (
        select(AimbatSnapshot)
        .join(
            subq,
            (col(AimbatSnapshot.event_id) == subq.c.event_id)
            & (col(AimbatSnapshot.time) == subq.c.max_time),
        )
        .options(
            selectinload(rel(AimbatSnapshot.event)).selectinload(
                rel(AimbatEvent.seismograms)
            ),
            selectinload(
                rel(AimbatSnapshot.seismogram_parameters_snapshots)
            ).selectinload(rel(AimbatSeismogramParametersSnapshot.parameters)),
            selectinload(rel(AimbatSnapshot.seismogram_quality_snapshots)).selectinload(
                rel(AimbatSeismogramQualitySnapshot.quality)
            ),
        )
    )

    snaps = session.exec(snap_stmt).all()

    all_records: list[AimbatSeismogramQualitySnapshot] = []
    selected_records: list[AimbatSeismogramQualitySnapshot] = []

    for snap in snaps:
        # Seismograms at this station in this snapshot.
        station_seis_ids = {
            seis.id for seis in snap.event.seismograms if seis.station_id == station_id
        }
        select_map = {
            sp.parameters.seismogram_id: sp.select
            for sp in snap.seismogram_parameters_snapshots
        }

        for sq in snap.seismogram_quality_snapshots:
            seis_id = sq.quality.seismogram_id
            if seis_id in station_seis_ids:
                all_records.append(sq)
                if select_map.get(seis_id, False):
                    selected_records.append(sq)

    return _stats_from_quality_snapshots(all_records), _stats_from_quality_snapshots(
        selected_records
    )


def dump_quality_event(session: Session, event_id: uuid.UUID) -> dict[str, Any]:
    """Return event MCCC quality as a JSON-serialisable dict.

    Reads from the most recent snapshot that has quality data. Returns null
    values for all fields when no MCCC has been run.

    Args:
        session: Database session.
        event_id: Event UUID.

    Returns:
        Flat dict with event quality and seismogram aggregate statistics.
        Timedelta values are serialised as total seconds (float).
    """
    event_quality, stats = get_quality_event(session, event_id)

    if event_quality is not None:
        result: dict[str, Any] = event_quality.model_dump(mode="json")
    else:
        result = {
            "event_id": str(event_id),
            **{k: None for k in AimbatEventQualityBase.model_fields},
        }

    result.update(_stats_dump(stats))
    return result


def dump_quality_station(session: Session, station_id: uuid.UUID) -> dict[str, Any]:
    """Return station quality as a JSON-serialisable dict.

    Aggregates seismogram quality across all events recorded at the station,
    with means and SEMs for all and selected seismograms.

    Args:
        session: Database session.
        station_id: Station UUID.

    Returns:
        Flat dict with seismogram aggregate statistics.
        Timedelta values are serialised as total seconds (float).
    """
    all_stats, selected_stats = get_quality_station(session, station_id)
    result: dict[str, Any] = {"station_id": str(station_id)}
    result.update(_stats_dump(all_stats))
    result.update(_stats_dump(selected_stats, prefix="selected_"))
    return result


# ---------------------------------------------------------------------------
# View functions
# ---------------------------------------------------------------------------


def seismogram_quality_groups(
    session: Session, seismogram_id: uuid.UUID
) -> list[FieldGroup]:
    """Return quality view data for a single seismogram.

    Args:
        session: Database session.
        seismogram_id: Seismogram UUID.

    Returns:
        A single-element list containing one `FieldGroup` with per-seismogram
        quality fields, or an empty group with a message if no quality data
        exists yet.
    """
    quality = get_quality_seismogram(session, seismogram_id)
    if quality is None:
        return [
            FieldGroup(
                title="",
                empty_message="No quality data — run MCCC first",
            )
        ]
    return [
        FieldGroup(
            title="",
            fields=_specs_from_model(quality, AimbatSeismogramQualityBase),
        )
    ]


def event_quality_groups(session: Session, event_id: uuid.UUID) -> list[FieldGroup]:
    """Return MCCC quality view data for an event.

    Args:
        session: Database session.
        event_id: Event UUID.

    Returns:
        Two `FieldGroup` instances: event-level statistics and
        averages across the seismograms used in the inversion.
    """
    event_quality, stats = get_quality_event(session, event_id)

    event_group = FieldGroup(title="Event statistics")
    if event_quality is not None:
        event_group.fields = _specs_from_model(event_quality, AimbatEventQualityBase)
    else:
        event_group.empty_message = "No event quality data — run MCCC first"

    return [
        event_group,
        FieldGroup(
            title=f"Averages across {stats.count} seismograms",
            fields=_specs_from_model(stats, SeismogramQualityStats),
        ),
    ]


def station_quality_groups(session: Session, station_id: uuid.UUID) -> list[FieldGroup]:
    """Return quality view data for a station.

    Args:
        session: Database session.
        station_id: Station UUID.

    Returns:
        Two `FieldGroup` instances: averages across selected seismograms
        and averages across all seismograms.
    """
    all_stats, selected_stats = get_quality_station(session, station_id)
    return [
        FieldGroup(
            title=f"Averages across {selected_stats.count} selected seismograms",
            fields=_specs_from_model(selected_stats, SeismogramQualityStats),
        ),
        FieldGroup(
            title=f"Averages across {all_stats.count} seismograms",
            fields=_specs_from_model(all_stats, SeismogramQualityStats),
        ),
    ]


def snapshot_quality_groups(
    session: Session, snapshot_id: uuid.UUID
) -> list[FieldGroup]:
    """Return MCCC quality view data for a snapshot.

    The number of groups depends on whether MCCC was run on all seismograms or
    only the selected ones, which is inferred from whether any non-selected
    seismogram has MCCC data in the snapshot.

    Args:
        session: Database session.
        snapshot_id: Snapshot UUID.

    Returns:
        Two `FieldGroup` instances: event-level MCCC statistics and
        per-seismogram averages (scoped to selected or all seismograms
        depending on how MCCC was run). Returns a single empty group
        when no quality was captured.

    Raises:
        ValueError: If no snapshot with the given ID is found.
    """
    snapshot = session.get(AimbatSnapshot, snapshot_id)
    if snapshot is None:
        raise ValueError(f"Snapshot {snapshot_id} not found.")

    if snapshot.event_quality_snapshot is None:
        return [
            FieldGroup(
                title="",
                empty_message="No quality data — run MCCC then create a snapshot",
            )
        ]

    eq = snapshot.event_quality_snapshot

    event_specs = _specs_from_model(eq, AimbatEventQualityBase)

    all_sq = [
        sq
        for sq in snapshot.seismogram_quality_snapshots
        if sq.mccc_cc_mean is not None
    ]
    stats = _stats_from_quality_snapshots(all_sq)

    return [
        FieldGroup(title="Event statistics", fields=event_specs),
        FieldGroup(
            title="Averages across seismograms",
            fields=_specs_from_model(stats, SeismogramQualityStats),
        ),
    ]
