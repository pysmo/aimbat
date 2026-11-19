"""Summaries shared by the commands that read picks."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aimbat.actions import PickSummary

__all__ = ["print_pick_summary"]


def print_pick_summary(picks: PickSummary, snapshotted_phases: int) -> None:
    """Print what became of the picks of an ingestion call, if there were any."""
    from rich.console import Console

    from aimbat.utils.formatters import fmt_timestamp

    if not (
        picks.stored
        or picks.already_present
        or picks.skipped_unnamed
        or picks.rematched
        or picks.changed
    ):
        return

    promoted = f"{picks.total_promoted} promoted"
    if picks.promoted:
        promoted += (
            " ("
            + ", ".join(f"{name}: {n}" for name, n in sorted(picks.promoted.items()))
            + ")"
        )
    counts = [
        f"{picks.stored} stored",
        f"{picks.matched} matched",
        promoted,
        f"{picks.unnamed} unnamed" if picks.unnamed else "",
        f"{picks.unmatched + picks.unresolved} without a seismogram"
        if picks.unmatched or picks.unresolved
        else "",
        f"{picks.already_present} already present" if picks.already_present else "",
        f"{picks.skipped_unnamed} unnamed skipped" if picks.skipped_unnamed else "",
        f"{picks.rematched} stored earlier and now matched" if picks.rematched else "",
    ]
    lines = ["Picks: " + ", ".join(c for c in counts if c) + "."]

    if picks.updated:
        updated = f"Updated {picks.updated} pick(s)"
        if picks.renamed:
            updated += (
                f", {picks.renamed} with a new phase name "
                + f"({picks.rows_deleted} row(s) deleted)"
            )
        lines.append(updated + ".")
    elif picks.changed:
        lines.append(
            f"{picks.changed} stored pick(s) differ from their data source. "
            + "`aimbat pick add --update` applies the changes."
        )

    left_out = [
        f"{len(picks.conflicts)} in conflict with an existing initial pick"
        if picks.conflicts
        else "",
        f"{len(picks.unpromoted)} of a phase not given with --phase"
        if picks.unpromoted
        else "",
        f"{len(picks.invalid)} invalid" if picks.invalid else "",
    ]
    if any(left_out):
        lines.append("Not promoted: " + ", ".join(c for c in left_out if c) + ".")

    created: dict[uuid.UUID, list[str]] = {}
    event_times = {}
    for phase in picks.phases_created:
        created.setdefault(phase.event_id, []).append(phase.name)
        event_times[phase.event_id] = phase.event_time
    lines.extend(
        f"Phases created for event {fmt_timestamp(event_times[event_id])}: "
        + ", ".join(sorted(names))
        + "."
        for event_id, names in created.items()
    )
    if snapshotted_phases:
        lines.append(f"Snapshotted {snapshotted_phases} phase(s).")

    Console().print("\n".join(lines))
