"""
Deduplicate events that were imported from sources reporting slightly different
origin times for the same earthquake.

Background
----------
``add_data_to_project`` deduplicates stations by SEED code
``(network, name, location, channel)`` — so importing the same station twice,
even with different coordinates, always reuses the existing record.  Station
duplicates therefore cannot arise through the normal import path.

Events are deduplicated by exact origin time.  When two data sources report
the same earthquake with origin times that differ by a second or two, they are
stored as *separate* ``AimbatEvent`` records. This script finds such
near-duplicate events, merges their seismograms into the canonical record
(the one with the most seismograms), averages the location and depth, then
removes the duplicates.

Run this script *before* starting any processing, and take a snapshot
afterwards so the clean state is recoverable.
"""

from pandas import Timedelta
from sqlmodel import Session, select

from aimbat.db import engine
from aimbat.models import AimbatEvent

# Merge events whose origin times differ by less than this value.
TIME_TOLERANCE = Timedelta(seconds=10)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _mean_opt(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def deduplicate_events(session: Session, tolerance: Timedelta = TIME_TOLERANCE) -> int:
    """Merge event records whose origin times are within *tolerance*.

    Events are sorted by time and clustered greedily: a new cluster begins
    whenever the gap to the previous event exceeds *tolerance*.

    For each cluster the record with the most seismograms is kept as the
    canonical entry; its location and depth are updated to the group mean.

    Returns the number of duplicate records removed.
    """
    events = sorted(
        session.exec(select(AimbatEvent)).all(),
        key=lambda e: e.time,
    )

    # Build clusters of near-simultaneous events.
    clusters: list[list[AimbatEvent]] = []
    for event in events:
        if clusters and event.time - clusters[-1][-1].time <= tolerance:
            clusters[-1].append(event)
        else:
            clusters.append([event])

    removed = 0
    for cluster in clusters:
        if len(cluster) < 2:
            continue

        canonical = max(cluster, key=lambda e: len(e.seismograms))
        duplicates = [e for e in cluster if e.id != canonical.id]

        # Set location / depth to the group mean.
        canonical.latitude = _mean([e.latitude for e in cluster])
        canonical.longitude = _mean([e.longitude for e in cluster])
        canonical.depth = _mean_opt([e.depth for e in cluster])

        for dup in duplicates:
            for seis in list(dup.seismograms):
                seis.event_id = canonical.id
                session.add(seis)
            session.flush()  # apply FK changes before deleting the row
            session.delete(dup)
            removed += 1

        session.add(canonical)

    session.commit()
    return removed


with Session(engine) as session:
    n = deduplicate_events(session)

print(f"Removed {n} duplicate event(s).")
