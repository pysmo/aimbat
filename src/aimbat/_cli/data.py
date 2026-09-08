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

`data add` automatically creates a snapshot for each event that received new
seismogram data, so there is no need to run `snapshot create` right after
ingestion (pass `--no-snapshot` to opt out for a given invocation). Use
`snapshot create` later for deliberate checkpoints, e.g. before trying an
experimental parameter change.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
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
    print_warning,
    use_event_parameter,
    use_station_parameter,
)

if TYPE_CHECKING:
    from aimbat.core import PruneReport
    from aimbat.models import AimbatDataSource

app = App(name="data", help=__doc__, help_format="markdown")


def _print_dry_run_results(
    added_datasources: Sequence[AimbatDataSource],
    existing_station_ids: set[uuid.UUID],
    existing_event_ids: set[uuid.UUID],
    existing_seismogram_ids: set[uuid.UUID],
    duplicate_warnings: Sequence[str],
) -> None:
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
                "source": str(ds.sourcename),
                "station": ds.seismogram.station_id not in existing_station_ids,
                "event": ds.seismogram.event_id not in existing_event_ids,
                "seismogram": ds.seismogram_id not in existing_seismogram_ids,
            }
            for ds in added_datasources
        ],
        model=_DryRunRow,
        title="Dry Run: Data to be added",
    )
    new_stations = sum(
        ds.seismogram.station_id not in existing_station_ids for ds in added_datasources
    )
    new_events = sum(
        ds.seismogram.event_id not in existing_event_ids for ds in added_datasources
    )
    new_seismograms = sum(
        ds.seismogram_id not in existing_seismogram_ids for ds in added_datasources
    )
    console = Console()
    console.print(
        f"\n{new_stations} station(s) added, "
        + f"{len(added_datasources) - new_stations} skipped. {new_events} "
        + f"event(s) added, {len(added_datasources) - new_events} skipped. "
        + f"{new_seismograms} seismogram(s) added, "
        + f"{len(added_datasources) - new_seismograms} skipped."
    )

    for message in duplicate_warnings:
        print_warning(message)


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
                "Automatically create a snapshot for each event that received new "
                + "seismogram data."
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

    Station and event deduplication is automatic: if a matching record already
    exists it is reused. Re-running `data add` on the same files is safe.

    Use `--dry-run` to preview what would be added without touching the
    database. Use `--no-snapshot` to skip the automatic post-ingestion
    snapshot for this invocation.

    Note `--dry-run` can still raise rather than produce a clean preview: an
    "ambiguous gap" near-duplicate event (see the module help above) is
    flagged as an error unconditionally, since it usually signals a data
    problem worth stopping for even during a preview.
    """
    from rich.progress import Progress

    from aimbat.core import add_data_to_project
    from aimbat.db import engine

    with Session(engine) as session:
        with Progress(disable=not show_progress_bar) as progress:
            task = progress.add_task("Adding data ...", total=len(data_sources))

            def on_progress(done: int, _total: int) -> None:
                progress.update(task, completed=done)

            (
                added_datasources,
                existing_station_ids,
                existing_event_ids,
                existing_seismogram_ids,
                duplicate_warnings,
            ) = add_data_to_project(
                session,
                data_sources,
                data_type,
                station_id=station_id,
                event_id=event_id,
                dry_run=dry_run,
                on_progress=on_progress,
            )

        if dry_run:
            _print_dry_run_results(
                added_datasources,
                existing_station_ids,
                existing_event_ids,
                existing_seismogram_ids,
                duplicate_warnings,
            )
        elif auto_snapshot:
            from aimbat.core import create_snapshots_for_added_data

            _snapshotted, failures = create_snapshots_for_added_data(
                session, added_datasources, existing_seismogram_ids
            )
            for event_id, error in failures:
                print_warning(
                    f"Could not create an automatic snapshot for event {event_id}: {error}"
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
    from rich import print_json

    from aimbat.core import dump_data_table
    from aimbat.db import engine

    with Session(engine) as session:
        print_json(data=dump_data_table(session, by_alias=dump_parameters.by_alias))


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


def _print_prune_report(
    report: PruneReport, *, will_prune_stations: bool, will_prune_events: bool
) -> None:
    """Print a `PruneReport` as a table plus follow-up warning lines."""
    from pydantic import BaseModel, Field
    from rich.console import Console

    from .common import json_to_table

    console = Console()

    if not report.orphan_seismograms:
        console.print("No vanished data sources found.")
    else:

        class _OrphanRow(BaseModel):
            source: str = Field(title="Source")
            type: str = Field(title="Type")
            station: str = Field(title="Station")
            event: str = Field(title="Event")
            reason: str = Field(title="Reason")

        rows = []
        for seis in report.orphan_seismograms:
            sourcename, datatype = report.orphan_sources[seis.id]
            rows.append(
                {
                    "source": sourcename,
                    "type": str(datatype),
                    "station": seis.station.name,
                    "event": seis.event.time.strftime("%Y-%m-%d %H:%M:%S"),
                    "reason": "source file missing",
                }
            )
        json_to_table(rows, model=_OrphanRow, title="Data sources to prune")

    for event in report.events_needing_invalidation:
        console.print(
            "Live ICCS/MCCC quality will be reset for event "
            + event.time.strftime("%Y-%m-%d %H:%M:%S")
            + " (re-run align / mccc)."
        )

    if report.emptied_stations:
        verb = "removed" if will_prune_stations else "left empty"
        console.print(f"{len(report.emptied_stations)} station(s) will be {verb}.")
    if report.emptied_events:
        if will_prune_events:
            console.print(
                f"{len(report.emptied_events)} emptied event(s) will be deleted."
            )
        else:
            console.print(
                f"{len(report.emptied_events)} event(s) will be left with no "
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
            help="Snapshot every affected event before pruning.",
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
    from aimbat.core import prune_project
    from aimbat.db import engine

    def confirm_prune(report: PruneReport) -> bool:
        _print_prune_report(
            report,
            will_prune_stations=prune_empty_stations,
            will_prune_events=prune_empty_events,
        )
        stations = len(report.emptied_stations) if prune_empty_stations else 0
        events = len(report.emptied_events) if prune_empty_events else 0
        confirm_or_abort(
            f"Delete {len(report.orphan_seismograms)} seismogram(s) "
            + f"(+ {stations} station(s), {events} event(s), "
            + f"{report.total_snapshots} snapshot(s), {report.total_notes} note(s))?",
            yes=confirm.yes,
        )
        return True

    with Session(engine) as session:
        report = prune_project(
            session,
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
        if dry_run or not report.orphan_seismograms:
            _print_prune_report(
                report,
                will_prune_stations=prune_empty_stations,
                will_prune_events=prune_empty_events,
            )


if __name__ == "__main__":
    app()
