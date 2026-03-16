"""Manage data sources in an AIMBAT project.

A *data source* is a file that AIMBAT reads seismogram waveforms and metadata
from. When a data source is added, AIMBAT extracts and stores the associated
station, event, and seismogram records in the project database — provided the
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
aimbat event default <ID>  # optionally set default event for future commands
```

Re-adding a data source that is already in the project is safe — existing
records are reused rather than duplicated.
"""

import uuid
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter, validators
from sqlmodel import Session

from aimbat.io import DataType

from .common import (
    DebugParameter,
    GlobalParameters,
    JsonDumpParameters,
    TableParameters,
    simple_exception,
    use_event_parameter,
    use_station_parameter,
)

app = App(name="data", help=__doc__, help_format="markdown")


@app.command(name="add")
@simple_exception
def cli_data_add(
    data_sources: Annotated[
        list[Path],
        Parameter(
            name="sources",
            help="One or more data source file paths to add.",
            consume_multiple=True,
            validator=validators.Path(exists=True),
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
    global_parameters: DebugParameter = DebugParameter(),
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
    database.
    """
    from aimbat.core import add_data_to_project
    from aimbat.db import engine

    disable_progress_bar = not show_progress_bar

    with Session(engine) as session:
        add_data_to_project(
            session,
            data_sources,
            data_type,
            station_id=station_id,
            event_id=event_id,
            dry_run=dry_run,
            disable_progress_bar=disable_progress_bar,
        )


@app.command(name="dump")
@simple_exception
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
@simple_exception
def cli_data_list(
    *,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print a table of data sources registered in the AIMBAT project."""
    from aimbat.core import dump_data_table, resolve_event
    from aimbat.db import engine
    from aimbat.logger import logger
    from aimbat.models import AimbatDataSource, AimbatSeismogram
    from aimbat.utils import json_to_table, uuid_shortener

    short = table_parameters.short

    with Session(engine) as session:
        logger.debug("Printing data sources table.")

        if global_parameters.all_events:
            data = dump_data_table(session, by_title=True)
            title = "Data sources for all events"
        else:
            event = resolve_event(session, global_parameters.event_id)
            data = dump_data_table(session, event.id, by_title=True)
            _time = event.time.strftime("%Y-%m-%d %H:%M:%S") if short else event.time
            _id = uuid_shortener(session, event) if short else event.id
            title = f"Data sources for event {_time} (ID={_id})"

        formatters = {
            "ID": lambda x: (
                uuid_shortener(session, AimbatDataSource, str_uuid=x) if short else x
            ),
            "Seismogram ID": lambda x: (
                uuid_shortener(session, AimbatSeismogram, str_uuid=x) if short else x
            ),
        }
        column_order = ["ID"]

        json_to_table(
            data,
            title=title,
            formatters=formatters,
            column_order=column_order,
        )


if __name__ == "__main__":
    app()
