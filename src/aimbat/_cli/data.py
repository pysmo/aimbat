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

import uuid
from .common import (
    GlobalParameters,
    TableParameters,
    simple_exception,
    ALL_EVENTS_PARAMETER,
    use_station_parameter,
    use_event_parameter,
)
from aimbat.models import AimbatEvent, AimbatStation, AimbatDataSource
from aimbat.io import DataType
from sqlmodel import Session, select
from cyclopts import App, Parameter, validators
from pathlib import Path
from typing import Annotated

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
    global_parameters: GlobalParameters = GlobalParameters(),
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
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Dump the contents of the AIMBAT data source table to JSON.

    Output can be piped or redirected for use in external tools or scripts.
    """
    from aimbat.db import engine
    from aimbat.core import dump_data_table_to_json
    from rich import print_json

    with Session(engine) as session:
        print_json(dump_data_table_to_json(session))


@app.command(name="list")
@simple_exception
def cli_data_list(
    *,
    all_events: Annotated[bool, ALL_EVENTS_PARAMETER] = False,
    table_parameters: TableParameters = TableParameters(),
    global_parameters: GlobalParameters = GlobalParameters(),
) -> None:
    """Print a table of data sources registered in the AIMBAT project."""
    from aimbat.db import engine
    from aimbat.core import get_active_event, get_data_for_event
    from aimbat.utils import uuid_shortener, make_table, TABLE_STYLING
    from aimbat.logger import logger
    from rich.console import Console

    short = table_parameters.short

    with Session(engine) as session:
        logger.info("Printing data sources table.")

        if all_events:
            aimbat_data_sources = session.exec(select(AimbatDataSource)).all()
            title = "Data sources for all events"
        else:
            active_event = get_active_event(session)
            aimbat_data_sources = get_data_for_event(session, active_event)
            time = (
                active_event.time.strftime("%Y-%m-%d %H:%M:%S")
                if short
                else active_event.time
            )
            id = uuid_shortener(session, active_event) if short else active_event.id
            title = f"Data sources for event {time} (ID={id})"

        logger.debug(f"Found {len(aimbat_data_sources)} data sources in total.")

        rows = [
            [
                uuid_shortener(session, a) if short else str(a.id),
                str(a.datatype),
                str(a.sourcename),
                (
                    uuid_shortener(session, a.seismogram)
                    if short
                    else str(a.seismogram.id)
                ),
            ]
            for a in aimbat_data_sources
        ]

        table = make_table(title=title)

        table.add_column(
            "ID (shortened)" if short else "ID",
            justify="center",
            style=TABLE_STYLING.id,
            no_wrap=True,
        )
        table.add_column("Datatype", justify="center", style=TABLE_STYLING.mine)
        table.add_column(
            "Source", justify="left", style=TABLE_STYLING.mine, no_wrap=True
        )
        table.add_column(
            "Seismogram ID", justify="center", style=TABLE_STYLING.linked, no_wrap=True
        )

        for row in rows:
            table.add_row(*row)

        console = Console()
        console.print(table)


if __name__ == "__main__":
    app()
