"""Read the picks of data sources that are already in the project.

A data source is read once by `add_data_to_project`. Its picks reach the
project again only through `add_picks_to_project`, which stores the new ones
and, if asked, applies the changed times and labels of the stored ones.
"""

import os
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from pandas import Timestamp
from sqlmodel import Session, col, select

from aimbat.io import DataType, read_source_records, supports_pick_reading
from aimbat.logger import logger
from aimbat.models import AimbatPick, AimbatSeismogram, AimbatSeismogramParameters

from ._data import _allowed_phases, _already_ingested_datasource
from ._picks import (
    PickChange,
    PickNaming,
    PromotionReport,
    StoreReport,
    promote_picks,
    store_picks,
)
from ._session import flush_deletes

__all__ = [
    "PickIngestReport",
    "UpdateReport",
    "add_picks_to_project",
    "update_picks",
]


@dataclass(frozen=True, slots=True)
class UpdateReport:
    """What `update_picks` changed."""

    updated: list[AimbatPick] = field(default_factory=list)
    """Picks given the time and label of their data source."""

    renamed: list[AimbatPick] = field(default_factory=list)
    """Updated picks whose phase name changed with their label."""

    rows_deleted: int = 0
    """Rows deleted because their pick changed its phase name."""


def update_picks(
    session: Session,
    changes: Sequence[PickChange],
    *,
    naming: PickNaming,
    end_times: Mapping[UUID, Timestamp] | None = None,
) -> UpdateReport:
    """Give stored picks the time and label their data source now gives.

    A pick whose label changed is named again from the new label. If its
    phase name changes, its row is deleted, so that it can be promoted under
    the new name. A promoted pick that keeps its name keeps its row, and the
    initial pick of the row changes with it. Nothing is promoted.

    Args:
        session: Database session.
        changes: The stored picks and the picks as read.
        naming: How picks are named again.
        end_times: End times of seismograms, keyed by seismogram ID, where
            known.

    Returns:
        The picks updated and renamed, and the number of rows deleted.

    Raises:
        ValueError: If a matched pick would lie before the begin time of its
            seismogram, or after its end time where known. Nothing is
            changed.
    """
    end_times = end_times or {}
    errors = []
    for change in changes:
        pick, read = change.pick, change.read
        if pick.seismogram_id is None:
            continue
        seismogram = session.get_one(AimbatSeismogram, pick.seismogram_id)
        described = f"The pick {pick.source_key!r} of {pick.source_name} at {read.time}"
        if read.time < seismogram.begin_time:
            errors.append(
                f"{described} lies before the begin time of seismogram "
                + f"{seismogram.id}."
            )
        end_time = end_times.get(seismogram.id)
        if end_time is not None and read.time > end_time:
            errors.append(
                f"{described} lies after the end time of seismogram "
                + f"{seismogram.id}."
            )
    if errors:
        raise ValueError(" ".join(errors))

    renamed: list[AimbatPick] = []
    for change in changes:
        pick, read = change.pick, change.read
        if read.label != pick.label:
            name = naming.name_for(read)
            if name != pick.phase_name:
                pick.phase_name = name
                renamed.append(pick)
        pick.time = read.time
        pick.label = read.label
        session.add(pick)

    rows = session.exec(
        select(AimbatSeismogramParameters).where(
            col(AimbatSeismogramParameters.pick_id).in_([p.id for p in renamed])
        )
    ).all()
    for row in rows:
        session.delete(row)
    flush_deletes(session)
    return UpdateReport([change.pick for change in changes], renamed, len(rows))


@dataclass(frozen=True, slots=True)
class PickIngestReport:
    """What `add_picks_to_project` did."""

    stored: StoreReport
    """Picks stored, skipped and found changed."""

    updated: UpdateReport
    """Changed picks updated. Empty unless updating was asked for."""

    promotion: PromotionReport
    """Rows and phases created from the stored and updated picks."""


def add_picks_to_project(
    session: Session,
    sources: Sequence[os.PathLike[str] | str],
    data_type: DataType,
    *,
    naming: PickNaming = PickNaming(),
    phases: Collection[str] | None = None,
    update: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> PickIngestReport:
    """Read the picks of data sources and store those that are new.

    A pick of a data source belongs to the seismogram of that source, so the
    data source must already be in the project. Picks whose source and key
    are stored are skipped, unless their time or label changed. Changed picks
    are reported, and updated with `update` (see `update_picks`). Dismissed
    picks are left as they are. New and updated picks that are named and
    matched are then promoted, as by `add_data_to_project`.

    Args:
        session: Database session.
        sources: Data sources to read.
        data_type: Data type of the data sources.
        naming: How picks are named.
        phases: Names of the phases the call may create or add rows to.
            Every phase if `None`.
        update: Whether to apply the changed times and labels.
        on_progress: Callback invoked as `on_progress(done, total)` after
            each data source.

    Returns:
        What was stored, updated and promoted.

    Raises:
        FileNotFoundError: If a data source does not exist.
        ValueError: If `data_type` holds no picks, a data source is not in
            the project, a name in `phases` is not a valid phase name, or a
            pick is invalid (see `store_picks` and `update_picks`).

    Anything raised while a data source is read carries a
    `Data source: <name>` note identifying it.
    """
    if not supports_pick_reading(data_type):
        raise ValueError(f"Data sources of type {data_type} hold no picks.")
    missing = [str(source) for source in sources if not Path(source).exists()]
    if missing:
        raise FileNotFoundError("Data source(s) not found: " + ", ".join(missing))
    allowed_phases = _allowed_phases(phases)

    reports: list[StoreReport] = []
    end_times: dict[UUID, Timestamp] = {}
    for done, source in enumerate(sources, start=1):
        name = str(source)
        try:
            records = read_source_records(
                source,
                data_type,
                station=False,
                event=False,
                seismogram=False,
                picks=True,
            )
            datasource = _already_ingested_datasource(session, name, data_type)
            seismogram = datasource.seismogram if datasource else None
            if seismogram is None and any(p.target is None for p in records.picks):
                raise ValueError(
                    f"{name} is not in the project. Add it with "
                    + "`aimbat data add` first."
                )
            if seismogram is not None and records.seismogram_end_time is not None:
                end_times[seismogram.id] = records.seismogram_end_time
            reports.append(
                store_picks(
                    session,
                    records.picks,
                    source_name=name,
                    source_type=data_type,
                    naming=naming,
                    source_seismogram=seismogram,
                    source_end_time=records.seismogram_end_time,
                )
            )
        except Exception as e:
            e.add_note(f"Data source: {source}")
            raise
        if on_progress is not None:
            on_progress(done, len(sources))

    stored = StoreReport.merge(reports)
    if update:
        updated = update_picks(
            session, stored.changed, naming=naming, end_times=end_times
        )
    else:
        updated = UpdateReport()
        if stored.changed:
            logger.info(
                f"{len(stored.changed)} stored pick(s) differ from their data "
                + "source and were left as they are."
            )
    promotion = promote_picks(
        session, [*stored.stored, *updated.updated], phases=allowed_phases
    )
    return PickIngestReport(stored, updated, promotion)
