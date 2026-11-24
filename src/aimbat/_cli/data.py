"""Manage data sources in an AIMBAT project.

A *data source* is where AIMBAT reads seismogram waveforms and metadata from.
Every current data type is a file, but a data source need not be one; it is
identified by an opaque `sourcename`. When a data source is added, AIMBAT
extracts and stores the associated station, event, and seismogram records in
the project database, provided the data type supports it.

**Supported data types** (`--type`):

- `sac` *(default)*: SAC waveform file. Extracts station, event, and seismogram
  data automatically.
- `json_station`: JSON file containing station metadata only. No seismogram is
  created.
- `json_event`: JSON file containing event metadata only. No seismogram is
  created.

**Typical workflow:**

```bash
aimbat project create
aimbat data add *.sac
aimbat event list          # list events created from SAC headers
```

Re-adding a data source that is already in the project is safe: existing
records are reused rather than duplicated.

Near-duplicate events (two files whose origin times differ by only a
sliver, most often from precision loss upstream such as SAC's `o`-header
32-bit float, rather than genuinely distinct events) are merged onto the
pre-existing event rather than turned into a second one. Merging is always
first-wins: the new data links to the pre-existing event's stored time and
location exactly as they already are, never merging, averaging, or
recomputing from the new file. Detection is controlled by
`event_duplicate_tolerance` (below this, a gap is assumed to be ordinary
precision noise and the existing event is reused with a warning),
`event_duplicate_raise_tolerance` (above `event_duplicate_tolerance` but
below this, a gap is treated as a likely data problem and always raises,
even during `--dry-run`; resolve it with `--use-event <uuid>` to link to
the pre-existing event explicitly), and `event_duplicate_strict` (skips
both checks entirely; with it set, events are only ever merged on an exact
origin-time match, which is itself only accurate to the microsecond AIMBAT
stores timestamps at, so any gap of a microsecond or more silently creates
a second event).

`data add` automatically creates a snapshot for each phase that gained
initial picks, so there is no need to run `snapshot create` right after
ingestion (pass `--no-snapshot` to opt out for a given invocation). Use
`snapshot create` later for deliberate checkpoints, e.g. before trying an
experimental parameter change.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from cyclopts import App, Parameter, validators
from sqlmodel import Session

from aimbat.io import DataType

from .common import (
    ConfirmParameters,
    DebugParameter,
    JsonDumpParameters,
    TableParameters,
    confirm_or_abort,
    event_parameter_is_all,
    event_parameter_with_all,
    handle_issues,
    phase_filter_parameter,
    print_json_dump,
    print_pick_summary,
    print_warning,
    use_event_parameter,
    use_station_parameter,
)

if TYPE_CHECKING:
    from aimbat.actions import AddDataResult, PruneResult, ReadinessReport

app = App(name="data", help=__doc__, help_format="markdown")


def _format_added_skipped(
    label: str, ids: set[uuid.UUID], new_ids: set[uuid.UUID]
) -> str:
    """Format one `N label(s) added, M skipped` clause of the dry-run summary.

    Args:
        label: Singular noun for the entity kind, e.g. `"station"`.
        ids: Distinct IDs of that kind touched by the ingestion call.
        new_ids: Those of `ids` that did not exist beforehand.
    """
    added = len(new_ids)
    return f"{added} {label}(s) added, {len(ids) - added} skipped"


def _print_dry_run_results(result: AddDataResult) -> None:
    """Print a summary table showing which entities were added vs skipped."""
    from pydantic import BaseModel, Field
    from rich.console import Console

    from .common import json_to_table

    class _DryRunRow(BaseModel):
        source: str = Field(title="Source")
        station: bool = Field(title="Station")
        event: bool = Field(title="Event")
        seismogram: bool = Field(title="Seismogram")

    json_to_table(
        [
            {
                "source": source.sourcename,
                "station": source.new_station,
                "event": source.new_event,
                "seismogram": source.new_seismogram,
            }
            for source in result.sources
        ],
        model=_DryRunRow,
        title="Dry Run: Data to be added",
    )
    # Counted over distinct entities, not over data sources: many sources
    # routinely resolve to one station or one event (a whole event's worth of
    # SAC files is the normal case), and counting per source reported that as
    # one station added per file.
    sources = result.sources
    console = Console()
    console.print(
        "\n"
        + ". ".join(
            _format_added_skipped(label, ids, new_ids)
            for label, ids, new_ids in (
                (
                    "station",
                    {s.station_id for s in sources},
                    {s.station_id for s in sources if s.new_station},
                ),
                (
                    "event",
                    {s.event_id for s in sources},
                    {s.event_id for s in sources if s.new_event},
                ),
                (
                    "seismogram",
                    {s.seismogram_id for s in sources},
                    {s.seismogram_id for s in sources if s.new_seismogram},
                ),
            )
        )
        + "."
    )

    for message in result.duplicate_warnings:
        print_warning(message)


def _print_added(result: AddDataResult) -> None:
    """Print the number of records an ingestion call created."""
    from rich.console import Console

    sources = result.sources
    seismograms = len({s.seismogram_id for s in sources if s.new_seismogram})
    stations = len({s.station_id for s in sources if s.new_station})
    events = len({s.event_id for s in sources if s.new_event})
    Console().print(
        f"Added {seismograms} seismogram(s), {stations} station(s), "
        + f"{events} event(s)."
    )


@app.command(name="add")
@handle_issues
def cli_data_add(
    data_sources: Annotated[
        list[Path],
        Parameter(
            name="sources",
            help="One or more data source paths to add.",
            consume_multiple=1,
            negative_iterable=(),
            validator=validators.Path(exists=True, dir_okay=False),
        ),
    ],
    *,
    data_type: Annotated[
        DataType,
        Parameter(
            name="type",
            help=(
                "Format of the data sources. Determines which metadata (station, "
                + "event, seismogram) can be extracted automatically."
            ),
        ),
    ] = DataType.SAC,
    station_id: Annotated[uuid.UUID | None, use_station_parameter()] = None,
    event_id: Annotated[uuid.UUID | None, use_event_parameter()] = None,
    unlabelled_as: Annotated[
        str | None,
        Parameter(
            name="unlabelled-as",
            help=(
                "Phase name given to picks that have no label in the data source. "
                + "Without it, such picks are stored but belong to no phase."
            ),
        ),
    ] = None,
    skip_unnamed: Annotated[
        bool,
        Parameter(
            name="skip-unnamed",
            help="Do not store picks that have no phase name.",
        ),
    ] = False,
    phases: Annotated[
        list[str] | None,
        Parameter(
            name="phase",
            negative_iterable=(),
            help=(
                "Phase that picks may be added to, or created for. Repeatable. "
                + "Named picks of other phases are stored but belong to no phase. "
                + "Without it, every phase."
            ),
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        Parameter(
            name="dry-run",
            help="Preview which records would be added without modifying the database.",
        ),
    ] = False,
    show_progress_bar: Annotated[
        bool,
        Parameter(
            name="progress", help="Display a progress bar while ingesting sources."
        ),
    ] = True,
    auto_snapshot: Annotated[
        bool,
        Parameter(
            name="snapshot",
            help=(
                "Automatically create a snapshot for each phase that gained "
                + "initial picks."
            ),
        ),
    ] = True,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Add or update data sources in the AIMBAT project.

    Each data source is processed according to `--type`. For `sac` (the
    default), AIMBAT extracts station, event, and seismogram metadata directly
    from the file. For types that cannot extract a station or event (e.g. a
    format that only carries waveform data), supply `--use-station` and/or
    `--use-event` to link to records that already exist in the project.

    Picks in the data sources become the initial picks of the phase their
    label names. SAC files keep the label of a pick in the `ka` or `kt0` to
    `kt9` header. Picks without a label are named with `--unlabelled-as`.
    Picks stored earlier without a matching seismogram are matched again
    once the data sources are added. A summary of the picks is printed at
    the end.

    Station and event deduplication is automatic: if a matching record already
    exists it is reused. Re-running `data add` on the same files is safe. An
    event holds one seismogram per station, so a second data source for the
    same station and event is refused.

    Use `--dry-run` to preview what would be added without touching the
    database. Use `--no-snapshot` to skip the automatic post-ingestion
    snapshot for this invocation.

    Note `--dry-run` can still raise rather than produce a clean preview: an
    "ambiguous gap" near-duplicate event (see the module help above) is
    flagged as an error unconditionally, since it usually signals a data
    problem worth stopping for even during a preview.
    """
    from rich.progress import Progress

    from aimbat.actions import add_data
    from aimbat.core import PickNaming

    naming = PickNaming(unlabelled_as=unlabelled_as, skip_unnamed=skip_unnamed)

    with Progress(disable=not show_progress_bar) as progress:
        task = progress.add_task("Adding data ...", total=len(data_sources))

        def on_progress(done: int, _total: int) -> None:
            progress.update(task, completed=done)

        result = add_data(
            data_sources,
            data_type,
            station_id=station_id,
            event_id=event_id,
            naming=naming,
            phases=phases,
            dry_run=dry_run,
            auto_snapshot=auto_snapshot,
            on_progress=on_progress,
        )

    if dry_run:
        _print_dry_run_results(result)
    else:
        _print_added(result)
    print_pick_summary(result.picks, len(result.snapshotted_phase_ids))
    for failed_id, error in result.snapshot_failures:
        print_warning(
            f"Could not create an automatic snapshot for phase {failed_id}: {error}"
        )
    if result.blocking_items:
        n = result.blocking_items
        print_warning(
            f"Not ready: {n} blocking item{'' if n == 1 else 's'}. "
            + "Run `aimbat data check`."
        )


@app.command(name="dump")
@handle_issues
def cli_data_dump(
    *,
    dump_parameters: JsonDumpParameters = JsonDumpParameters(),
) -> None:
    """Dump AIMBAT datasources table as a JSON string.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.core import dump_data_table

    print_json_dump(dump_data_table, by_alias=dump_parameters.by_alias)


@app.command(name="list")
@handle_issues
def cli_data_list(
    event_id: Annotated[uuid.UUID | Literal["all"], event_parameter_with_all()],
    *,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Print a table of data sources registered in the AIMBAT project."""
    from aimbat.core import dump_data_table, resolve_event
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.models import AimbatDataSource, AimbatSeismogram
    from aimbat.models._format import RichColSpec
    from aimbat.utils import uuid_shortener

    from .common import json_to_table

    raw = table_parameters.raw

    with Session(engine) as session:
        logger.debug("Printing data sources table.")

        if event_parameter_is_all(event_id):
            data = dump_data_table(session)
            title = "Data sources for all events"
        else:
            event = resolve_event(session, event_id)
            data = dump_data_table(session, event.id)
            _time = event.time.strftime("%Y-%m-%d %H:%M:%S") if not raw else event.time
            _id = uuid_shortener(session, event) if not raw else event.id
            title = f"Data sources for event {_time} (ID={_id})"

        col_specs = {
            "id": RichColSpec(
                formatter=lambda x: uuid_shortener(
                    session, AimbatDataSource, str_uuid=x
                )
            ),
            "seismogram_id": RichColSpec(
                formatter=lambda x: uuid_shortener(
                    session, AimbatSeismogram, str_uuid=x
                )
            ),
        }

        json_to_table(
            model=AimbatDataSource,
            data=data,
            title=title,
            raw=raw,
            col_specs=col_specs,
        )


_PROBLEMS = {
    "unnamed_pick": "unnamed pick",
    "unmatched_pick": "unmatched pick",
    "ambiguous_pick": "ambiguous pick",
    "empty_phase": "empty phase",
    "unpromoted_picks": "unpromoted pick",
    "conflicting_pick": "conflicting pick",
    "unresolved_event": "unknown event",
    "seismogram_without_picks": "seismogram without pick",
    "pick_after_end": "pick after end",
}


def _print_readiness(report: ReadinessReport, *, raw: bool) -> None:
    """Print readiness items as a table, followed by a one-line verdict."""
    from rich.console import Console
    from rich.table import Table

    from aimbat.db import engine
    from aimbat.models import AimbatEvent, AimbatPick, AimbatSeismogram, AimbatTypes
    from aimbat.utils.formatters import fmt_timestamp

    from .common import id_label

    console = Console()
    if report.items:
        table = Table()
        for header in ("Event", "Phase", "Severity", "Problem", "Count", "Fix"):
            table.add_column(header, overflow="fold")
        with Session(engine) as session:
            for item in report.items:
                if item.event_id is None:
                    event, phase = "-", "-"
                else:
                    time = session.get_one(AimbatEvent, item.event_id).time
                    label = id_label(session, AimbatEvent, item.event_id, raw=raw)
                    event = f"{fmt_timestamp(time)} ({label})"
                    phase = item.phase_name or "(all)"
                fixes = "\n".join(item.fixes)
                if not raw:
                    ids: list[tuple[type[AimbatTypes], uuid.UUID]] = (
                        [(AimbatEvent, item.event_id)] if item.event_id else []
                    )
                    ids += [(AimbatPick, i) for i in item.pick_ids]
                    ids += [(AimbatSeismogram, i) for i in item.seismogram_ids]
                    for model, record_id in ids:
                        fixes = fixes.replace(
                            str(record_id),
                            id_label(session, model, record_id, raw=False),
                        )
                table.add_row(
                    event,
                    phase,
                    str(item.severity),
                    _PROBLEMS[item.kind],
                    str(item.count),
                    fixes,
                    style="red" if item.blocking else None,
                )
        console.print(table)

    scope = f"{report.events} event(s), {report.phases} phase(s)"
    blocking = len(report.blocking)
    notices = len(report.items) - blocking
    if blocking:
        console.print(f"Not ready: {scope}, {blocking} blocking item(s).")
    elif notices:
        console.print(f"Ready: {scope}, no blocking items, {notices} notice(s).")
    else:
        console.print(f"Ready: {scope}, no blocking items.")


@app.command(name="check")
@handle_issues
def cli_data_check(
    event_id: Annotated[uuid.UUID | Literal["all"], event_parameter_with_all()] = "all",
    *,
    phase: Annotated[str | None, phase_filter_parameter()] = None,
    strict: Annotated[
        bool,
        Parameter(name="strict", help="Exit with status 2 for notices as well."),
    ] = False,
    as_json: Annotated[
        bool,
        Parameter(name="json", help="Print the items as JSON instead of a table."),
    ] = False,
    table_parameters: TableParameters = TableParameters(),
) -> None:
    """Check whether the data are ready for processing.

    Lists what prevents processing (blocking items) and what may need
    attention (notices), such as picks without a phase name, picks that match
    no seismogram, or phases without initial picks, each with the command
    that fixes it. Alignment of a phase is refused while a blocking item
    applies to it. Without an event, every event is checked, together with
    the picks whose event is not in the project.

    The exit status is 0 when nothing blocks, 1 when the check itself fails,
    and 2 when an item blocks, or with `--strict` when any item is found.
    """
    import sys

    from aimbat.actions import check_data

    report = check_data(event_id, phase_name=phase)
    if as_json:
        from dataclasses import asdict

        from rich import print_json

        print_json(data=[asdict(item) for item in report.items], default=str)
    else:
        _print_readiness(report, raw=table_parameters.raw)

    if report.blocking or (strict and report.items):
        sys.exit(2)


def _print_prune_report(
    report: PruneResult, *, will_prune_stations: bool, will_prune_events: bool
) -> None:
    """Print a `PruneResult` as a table plus follow-up warning lines."""
    from pydantic import BaseModel, Field
    from rich.console import Console

    from .common import json_to_table

    console = Console()

    if not report.orphans:
        console.print("No vanished data sources found.")
    else:

        class _OrphanRow(BaseModel):
            source: str = Field(title="Source")
            type: str = Field(title="Type")
            station: str = Field(title="Station")
            event: str = Field(title="Event")
            reason: str = Field(title="Reason")

        rows = []
        for orphan in report.orphans:
            rows.append(
                {
                    "source": orphan.sourcename,
                    "type": str(orphan.datatype),
                    "station": orphan.station_name,
                    "event": orphan.event_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "reason": "source file missing",
                }
            )
        json_to_table(rows, model=_OrphanRow, title="Data sources to prune")

    for event_time in report.events_losing_seismograms.values():
        console.print(
            "Event "
            + event_time.strftime("%Y-%m-%d %H:%M:%S")
            + " loses seismograms: its ICCS/MCCC quality may need re-running "
            + "(align / mccc)."
        )

    if report.emptied_station_ids:
        verb = "removed" if will_prune_stations else "left empty"
        console.print(f"{len(report.emptied_station_ids)} station(s) will be {verb}.")
    if report.emptied_event_ids:
        if will_prune_events:
            console.print(
                f"{len(report.emptied_event_ids)} emptied event(s) will be deleted."
            )
        else:
            console.print(
                f"{len(report.emptied_event_ids)} event(s) will be left with no "
                + "seismograms (pass --prune-empty-events to delete them)."
            )

    if report.total_snapshots:
        print_warning(
            f"{report.total_snapshots} snapshot(s) will be permanently deleted."
        )
    for category, count in report.cascaded_notes.items():
        print_warning(f"{count} {category} note(s) will be deleted.")
    for message in report.warnings:
        print_warning(message)


@app.command(name="prune")
@handle_issues
def cli_data_prune(
    event_id: Annotated[uuid.UUID | Literal["all"], event_parameter_with_all()],
    *,
    dry_run: Annotated[
        bool,
        Parameter(
            name="dry-run",
            help="Show what would be pruned without deleting anything.",
        ),
    ] = False,
    force: Annotated[
        bool,
        Parameter(
            help=(
                "Treat a source whose presence cannot be determined (an "
                + "unreadable file, a missing parent directory, an unreachable "
                + "mount) as vanished instead of stopping."
            ),
        ),
    ] = False,
    prune_empty_stations: Annotated[
        bool,
        Parameter(
            name="prune-empty-stations",
            help="Also delete stations left with no seismograms.",
        ),
    ] = False,
    prune_empty_events: Annotated[
        bool,
        Parameter(
            name="prune-empty-events",
            help=(
                "Also delete events left with no seismograms. This permanently "
                + "destroys those events' snapshot history."
            ),
        ),
    ] = False,
    auto_snapshot: Annotated[
        bool,
        Parameter(
            name="snapshot",
            help="Snapshot every phase that loses seismograms before pruning.",
        ),
    ] = True,
    confirm: ConfirmParameters = ConfirmParameters(),
) -> None:
    """Delete seismograms whose data source has vanished.

    Reconciles the project with reality after a waveform source is removed (a
    SAC file deleted, a directory moved). Each seismogram whose source can no
    longer be read is deleted, along with its data source, parameters, and
    quality records. Frozen snapshot history is preserved.

    `prune` never deletes anything the source still provides. To remove a
    seismogram whose data still exist, remove it from the source directory
    first; to exclude one from analysis without deleting it, set `select =
    False` instead.

    Always run with `--dry-run` first: `prune` cannot tell a relocated file
    from a deleted one. Pass `--prune-empty-stations` / `--prune-empty-events`
    to also clean up stations or events left with no seismograms.
    """
    from aimbat.actions import prune_data

    def confirm_prune(report: PruneResult) -> bool:
        _print_prune_report(
            report,
            will_prune_stations=prune_empty_stations,
            will_prune_events=prune_empty_events,
        )
        stations = len(report.emptied_station_ids) if prune_empty_stations else 0
        events = len(report.emptied_event_ids) if prune_empty_events else 0
        confirm_or_abort(
            f"Delete {len(report.orphans)} seismogram(s) "
            + f"(+ {stations} station(s), {events} event(s), "
            + f"{report.total_snapshots} snapshot(s), {report.total_notes} note(s))?",
            yes=confirm.yes,
        )
        return True

    report = prune_data(
        event_id,
        dry_run=dry_run,
        prune_empty_stations=prune_empty_stations,
        prune_empty_events=prune_empty_events,
        auto_snapshot=auto_snapshot,
        force=force,
        confirm=None if dry_run else confirm_prune,
    )
    # A dry run, or a live run with nothing to prune, never reaches the
    # confirm callback, so the report is still unprinted here.
    if dry_run or not report.orphans:
        _print_prune_report(
            report,
            will_prune_stations=prune_empty_stations,
            will_prune_events=prune_empty_events,
        )


if __name__ == "__main__":
    app()
