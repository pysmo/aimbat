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

```
aimbat project create
aimbat data add *.sac
aimbat event list          # find the event ID
aimbat event activate <ID>
```

Re-adding a data source that is already in the project is safe — existing
records are reused rather than duplicated.
"""

from .common import (
    GlobalParameters,
    TableParameters,
    simple_exception,
    ALL_EVENTS_PARAMETER,
    use_station_parameter,
    use_event_parameter,
)
from aimbat.models import AimbatEvent, AimbatStation
from aimbat.io import DataType
from sqlmodel import Session
from cyclopts import App, Parameter, validators
from pathlib import Path
from typing import Annotated
import uuid

app = App(name="data", help=__doc__, help_format="markdown")


@app.command(name="add")
@simple_exception
def cli_data_add(
    data_sources: Annotated[
        list[Path],
        Parameter(
            name="sources",
            consume_multiple=True,
            validator=validators.Path(exists=True),
        ),
    ],
    *,
    data_type: Annotated[DataType, Parameter(name="type")] = DataType.SAC,
    station_id: Annotated[
        uuid.UUID | None, use_station_parameter(AimbatStation)
    ] = None,
    event_id: Annotated[uuid.UUID | None, use_event_parameter(AimbatEvent)] = None,
    dry_run: Annotated[bool, Parameter(name="dry-run")] = False,
    show_progress_bar: Annotated[bool, Parameter(name="progress")] = True,
    global_parameters: GlobalParameters | None = None,
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

    Args:
        data_sources: One or more data source paths to add.
        data_type: Format of the data sources. Determines which metadata
            (station, event, seismogram) can be extracted automatically.
        dry_run: Preview which records would be added without modifying the
            database.
        show_progress_bar: Display a progress bar while ingesting sources.
    """
    from aimbat.db import engine
    from aimbat.core import add_data_to_project

    global_parameters = global_parameters or GlobalParameters()

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


@app.command(name="list")
@simple_exception
def cli_data_list(
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print a table of data sources registered in the AIMBAT project."""
    from aimbat.db import engine
    from aimbat.core import print_data_table

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_data_table(session, table_parameters.short, all_events)


@app.command(name="dump")
@simple_exception
def cli_data_dump(
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Dump the contents of the AIMBAT data source table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.db import engine
    from aimbat.core import dump_data_table_to_json
    from rich import print_json

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_json(dump_data_table_to_json(session))


if __name__ == "__main__":
    app()
