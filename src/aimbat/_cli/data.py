"""Manage data sources in an AIMBAT project.

A *data source* is a file that AIMBAT reads seismogram waveforms and metadata
from. When a data source is added, AIMBAT extracts and stores the associated
station, event, and seismogram records in the project database, provided the
data type supports it.

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
32-bit float, rather than genuinely distinct events) are flagged rather
than silently merged. Resolving a flagged conflict is always first-wins:
`--use-event <uuid>` links the new data to the pre-existing event's stored
time and location exactly as they already are, it never merges, averages,
or recomputes from the new file. Detection is controlled by
`event_duplicate_tolerance` (below this, a gap is assumed to be ordinary
precision noise), `event_duplicate_raise_tolerance` (above
`event_duplicate_tolerance` but below this, a gap is treated as a likely
data problem and always raises, even during `--dry-run`), and
`event_duplicate_strict` (skips both checks entirely; with it set, events
are only ever merged on an exact origin-time match, which is itself only
accurate to the microsecond AIMBAT stores timestamps at, so any gap of a
microsecond or more silently creates a second event).

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
    DebugParameter,
    JsonDumpParameters,
    TableParameters,
    event_parameter_is_all,
    event_parameter_with_all,
    handle_issues,
    use_event_parameter,
    use_station_parameter,
)

if TYPE_CHECKING:
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
    from .common._decorators import _print_warning

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
        f"{len(added_datasources) - new_stations} skipped. "
        f"{new_events} event(s) added, "
        f"{len(added_datasources) - new_events} skipped. "
        f"{new_seismograms} seismogram(s) added, "
        f"{len(added_datasources) - new_seismograms} skipped."
    )

    for message in duplicate_warnings:
        _print_warning(message)


def _create_snapshots_for_touched_events(
    session: Session,
    added_datasources: Sequence[AimbatDataSource],
    existing_seismogram_ids: set[uuid.UUID],
) -> None:
    """Create one snapshot per event that received a newly created seismogram."""
    from collections import Counter

    from aimbat.core import create_snapshot
    from aimbat.logger import logger
    from aimbat.models import AimbatEvent

    from .common._decorators import _print_warning

    new_seismogram_counts: Counter[uuid.UUID] = Counter(
        ds.seismogram.event_id
        for ds in added_datasources
        if ds.seismogram_id not in existing_seismogram_ids
    )

    for event_id, count in new_seismogram_counts.items():
        event = session.get(AimbatEvent, event_id)
        if event is None:
            continue
        comment = f"Added {count} seismogram{'' if count == 1 else 's'}"
        try:
            create_snapshot(session, event, comment=comment, automatic=True)
        except Exception as e:
            # By this point add_data_to_project has already committed the
            # seismogram data, so a snapshot failure must not be reported as
            # a `data add` failure - that would misleadingly suggest the data
            # itself wasn't added. Warn and move on to the next event rather
            # than raising, so one event's snapshot failure (e.g. an
            # unexpected quality-data shape) can't suppress the baseline for
            # an unrelated event touched in the same call. A failed commit
            # leaves the session unusable until rolled back, which would
            # otherwise make every subsequent event's snapshot fail too.
            session.rollback()
            logger.warning(
                f"Failed to create automatic snapshot for event {event_id}: {e}"
            )
            _print_warning(
                f"Could not create an automatic snapshot for event {event_id}: {e}"
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
            help="Format of the data sources. Determines which metadata"
            " (station, event, seismogram) can be extracted automatically.",
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
            help="Automatically create a snapshot for each event that received "
            "new seismogram data.",
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
            _create_snapshots_for_touched_events(
                session, added_datasources, existing_seismogram_ids
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


if __name__ == "__main__":
    app()
