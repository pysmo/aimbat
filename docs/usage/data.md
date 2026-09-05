# Adding data

## How AIMBAT stores data

AIMBAT never modifies input files. When a data source is added, AIMBAT reads the
metadata it needs (event location, station coordinates, initial pick time) and
stores copies in the project database. After import, the original files are only
accessed to read waveform samples.

Each file is validated before any record is written: required fields present,
values in range, types correct. A file that fails validation is skipped and the
database is left unchanged for it. Other files in the same batch still import.

!!! warning "Files must remain accessible"

    AIMBAT stores the path to each data file at import time. If a file is moved,
    renamed, or deleted afterwards, AIMBAT can no longer read waveform data for
    the associated seismogram. Keep data files in a stable location, or update
    the path in the database before moving them.

## Data types

AIMBAT reads three data types, selected with `--type`:

| Type         | Flag                     | What it provides                              |
| ------------ | ------------------------ | --------------------------------------------- |
| SAC          | `--type sac` *(default)* | Station + event + seismogram waveform         |
| JSON event   | `--type json_event`      | Event metadata only, no seismogram created    |
| JSON station | `--type json_station`    | Station metadata only, no seismogram created  |

`--type` defaults to `sac`, so it only needs to be given for JSON. Both JSON
variants use the `.json` extension, so `--type` is what tells them apart. The TUI
file picker filters by extension (`.sac`, `.bhz`, `.bhn`, `.bhe` for SAC); the
CLI reads whatever paths it is given as the requested type.

See [`aimbat data add`][aimbat._cli.data.cli_data_add] for the full set of flags,
including `--use-event`, `--use-station`, `--dry-run`, and `--no-snapshot`.

## Adding SAC files

The common case is SAC files in one or more directories, each carrying station
and event headers and an initial pick:

=== "CLI"

    ```bash
    aimbat data add *.sac
    ```

=== "Shell"

    ```bash
    data add file1.sac file2.sac
    ```

    Glob patterns like `*.sac` don't expand here: `aimbat shell` has no shell
    of its own to do that. List files explicitly, or use the CLI at a normal
    prompt for glob-based imports.

=== "TUI"

    Press `d`, choose **SAC**, then pick a file. The picker adds one file at a
    time and can't select multiple files or a directory; repeat for each one.

=== "API"

    ```python
    from pathlib import Path

    from sqlmodel import Session
    from aimbat.core import add_data_to_project
    from aimbat.db import engine
    from aimbat.io import DataType

    with Session(engine) as session:
        add_data_to_project(session, sorted(Path().glob("*.sac")), DataType.SAC)
    ```

Import deduplicates, so the same command is safe to re-run:

```bash
aimbat data add *.sac          # first run: imports everything
aimbat data add *.sac          # second run: no-op, all files already known
```

### Initial picks

SAC files carry named time markers (`T0`–`T9`). AIMBAT reads one of them as the
initial phase pick (`t0` in AIMBAT's terms). The default is `T0`; change it with
`AIMBAT_SAC_PICK_HEADER`, per command or in `.env`:

```bash title=".env"
AIMBAT_SAC_PICK_HEADER=t1
```

### Selecting subsets

Standard shell glob patterns apply, at a normal command-line prompt:

=== "CLI"

    ```bash
    aimbat data add event1/*.sac           # one subdirectory
    aimbat data add data/**/*.sac          # recursive (bash 4+ with globstar; zsh)
    aimbat data add data/*/BHZ.sac         # vertical component only
    aimbat data add data/II.*.BHZ.sac      # network filter
    ```

=== "Shell"

    Not supported: these all rely on shell glob expansion, which `aimbat
    shell` has no shell of its own to perform. Use the CLI, or list the
    matching files explicitly.

## How events are matched and de-duplicated

Event matching applies to SAC and `--type json_event` imports alike.

AIMBAT links a newly imported event to an existing one only if its origin time is
**exactly** equal to that event's stored time, to the microsecond (the precision
AIMBAT stores timestamps at). Otherwise it does not reuse that event.

A new origin time that nearly, but not exactly, matches an existing event's time
is not silently turned into a second event. How close counts as "near" is
controlled by `event_duplicate_tolerance` and `event_duplicate_raise_tolerance`
(see [Aimbat Defaults](defaults.md)):

- Within `event_duplicate_tolerance` (default {{ event_duplicate_tolerance }}),
  the existing event is reused, exactly as an exact time match is, with a
  warning naming both origin times and the gap (a `--dry-run` reports the same
  in its preview). A gap this small is usually timestamp precision loss
  upstream, such as the classic v6 SAC header's 32-bit float `o` field not
  round-tripping identically across files, rather than a genuinely distinct
  event.
- Beyond that but within `event_duplicate_raise_tolerance` (default
  {{ event_duplicate_raise_tolerance }}), import always raises, even during
  `--dry-run`. A gap this size usually signals a real timing problem in the
  source data, worth investigating before import.
- Beyond `event_duplicate_raise_tolerance`, the new origin time is treated as a
  genuinely independent event, with no warning.

The check runs against every event AIMBAT already knows about when a file is
processed, including events created earlier in the same `data add` call.
Reuse is always first-wins: the new import links to the existing event's stored
time and location exactly as they are. It never merges, averages, or recomputes
from the new data. In the ambiguous-gap band, re-run with `--use-event <ID>` to
link explicitly to the existing event and get past the error.

!!! warning "Use SAC header version 7, or provide the event explicitly"

    Write files with `NVHDR=7`; its double-precision footer avoids the classic
    header's rounding issue. Otherwise, supply the event once from a JSON file
    and link every SAC file to it with `--use-event <ID>`, bypassing SAC-derived
    time matching entirely. See [Supplying a missing event](#supplying-a-missing-event).

!!! note "Turning near-duplicate detection off"

    `event_duplicate_strict` (see [Aimbat Defaults](defaults.md)) skips both
    tolerance checks, leaving only the exact-time match: any gap of a microsecond
    or more then creates a fully independent event with no warning. Use it only
    when the source data are trusted to be free of timing problems at that
    precision, for example a catalogue known to contain legitimately close but
    genuinely distinct events such as an aftershock swarm.

## Previewing before import

`--dry-run` shows what would be added without touching the database, for any
`--type`:

=== "CLI"

    ```bash
    aimbat data add --dry-run *.sac
    ```

=== "Shell"

    ```bash
    data add --dry-run file1.sac file2.sac
    ```

=== "API"

    ```python
    (
        added_datasources,
        existing_station_ids,
        existing_event_ids,
        existing_seismogram_ids,
        duplicate_warnings,
    ) = add_data_to_project(session, paths, DataType.SAC, dry_run=True)
    ```

The TUI has no equivalent; its file picker imports as soon as a file is chosen.

The CLI and shell print which stations, events, and seismograms would be newly
created versus already known (a near-duplicate within `event_duplicate_tolerance`
shows as a reused event); the API returns the same information. Either way, a
dry run surfaces any ambiguous-gap conflict a real run would raise.
That makes it worth running as routine practice before a new batch: catching an
ambiguous-gap conflict here means resolving it up front with `--use-event <ID>`
rather than hitting it partway through a real import, which aborts the whole
batch and rolls back everything already added in that call.

A gap in the ambiguous band raises during `--dry-run` just as it does on a real
import.

## Automatic snapshots

An import snapshots every event that receives at least one newly imported
seismogram, at the end of the call. This happens regardless of `--type`, and
gives a baseline to roll back to before any processing begins. Re-importing
files already in the project creates no new snapshot, since nothing changed.

=== "CLI"

    ```bash
    aimbat data add --no-snapshot *.sac  # skip it for this invocation
    ```

=== "Shell"

    ```bash
    data add --no-snapshot file1.sac file2.sac
    ```

=== "TUI"

    Always snapshots; there's no toggle to skip it.

=== "API"

    [`add_data_to_project`][aimbat.core.add_data_to_project] never snapshots on
    its own, unlike the CLI, shell, and TUI. Call
    [`create_snapshot`][aimbat.core.create_snapshot] explicitly for one:

    ```python
    from aimbat.core import create_snapshot

    create_snapshot(session, event, comment="import")
    ```

See [Snapshots](snapshots.md) for working with snapshots generally.

## Missing event or station metadata

SAC files from some sources omit event or station headers. Add the metadata from
a JSON file first, then link the SAC files to the resulting record.

The TUI has no equivalent for either: its file picker can't link an import to a
pre-existing event or station. Use the CLI, shell, or API instead.

### Supplying a missing event

=== "CLI"

    ```bash
    aimbat data add --type json_event event.json
    aimbat data add --use-event <EVENT_ID> --type sac *.sac
    ```

=== "Shell"

    ```bash
    data add --type json_event event.json
    data add --use-event <EVENT_ID> --type sac file1.sac file2.sac
    ```

=== "API"

    ```python
    from sqlmodel import Session, select
    from aimbat.core import add_data_to_project
    from aimbat.db import engine
    from aimbat.io import DataType
    from aimbat.models import AimbatEvent

    with Session(engine) as session:
        add_data_to_project(session, [event_json], DataType.JSON_EVENT)
        event = session.exec(select(AimbatEvent)).one()
        add_data_to_project(session, sac_files, DataType.SAC, event_id=event.id)
    ```

`--use-event` accepts a full UUID or any unique prefix from `aimbat event list`.

### Supplying a missing station

=== "CLI"

    ```bash
    aimbat data add --type json_station station.json
    aimbat data add --use-station <STATION_ID> --type sac waveform.sac
    ```

=== "Shell"

    ```bash
    data add --type json_station station.json
    data add --use-station <STATION_ID> --type sac waveform.sac
    ```

=== "API"

    ```python
    from sqlmodel import Session, select
    from aimbat.core import add_data_to_project
    from aimbat.db import engine
    from aimbat.io import DataType
    from aimbat.models import AimbatStation

    with Session(engine) as session:
        add_data_to_project(session, [station_json], DataType.JSON_STATION)
        station = session.exec(select(AimbatStation)).one()
        add_data_to_project(
            session, [waveform_sac], DataType.SAC, station_id=station.id
        )
    ```

### JSON format

JSON event and station files must match the structure of
[`AimbatEvent`][aimbat.models.AimbatEvent] and
[`AimbatStation`][aimbat.models.AimbatStation]. Use `aimbat event dump` or
`aimbat station dump` to export existing records as templates.

**Event:**

```json
{
    "time": "2024-03-15T14:22:11Z",
    "latitude": 37.5,
    "longitude": 143.0,
    "depth": 35.0
}
```

**Station:**

```json
{
    "name": "ANMO",
    "network": "IU",
    "location": "00",
    "channel": "BHZ",
    "latitude": 34.946,
    "longitude": -106.457,
    "elevation": 1820.0
}
```

Records are identified by random UUIDs, so JSON exported from one AIMBAT project
imports into another with no risk of ID collisions.

## Ingesting seismograms directly

`add_data_to_project` reads from a file AIMBAT already understands (`SAC`,
`JSON_STATION`, `JSON_EVENT`). `add_seismograms_to_project` is the
counterpart for a caller that already has pysmo objects in memory, fetched
from a web service, built in a notebook, or produced by a library such as
[`pysmo.tools.project.PysmoProject`][], with no file round-trip required.
It takes a list of `(seismogram, station, event)` triples, built from
anything shaped like pysmo's
[`IccsSeismogram`][pysmo.tools.iccs.IccsSeismogram],
[`Station`][pysmo.Station], and [`Event`][pysmo.Event] protocols:

```python
--8<-- "docs/snippets/api_ingest_seismograms.py"
```

!!! tip "Where the data end up"

    Each seismogram's waveform is written as a miniSEED file under `data_dir`
    (created automatically if it doesn't exist), so it can be read back later
    like any other data source. Station and event metadata come directly from
    the objects given, not from that file.

    If the seismogram was fetched remotely, as above, this write is its only
    copy on disk. If it instead came from a local file already on disk,
    `data_dir` becomes a second, redundant copy.

`PysmoProject` is just one possible producer; any object with the right shape
works identically, including one built by hand.

Every triple must carry a real `Event`: as with `add_data_to_project`, a
seismogram cannot exist in AIMBAT without one. Reuse the same `Event` object
across several triples, as above, to link them to a single `AimbatEvent`. The
same near-duplicate detection described in
[How events are matched and de-duplicated](#how-events-are-matched-and-de-duplicated)
applies.

## Checking the import

=== "CLI"

    ```bash
    aimbat data list              # data sources for the default event
    aimbat data list all          # all data sources in the project
    aimbat event list             # events extracted from imported files
    aimbat station list           # stations extracted from imported files
    aimbat seismogram list        # seismograms for the default event
    ```

=== "Shell"

    ```bash
    data list
    data list all
    event list
    station list
    seismogram list
    ```

=== "TUI"

    The **Project** tab lists events and stations; the **Live data** tab lists
    seismograms for the selected event.

=== "API"

    ```python
    from sqlmodel import Session, select
    from aimbat.db import engine
    from aimbat.models import AimbatDataSource, AimbatEvent, AimbatSeismogram, AimbatStation

    with Session(engine) as session:
        data_sources = session.exec(select(AimbatDataSource)).all()
        events = session.exec(select(AimbatEvent)).all()
        stations = session.exec(select(AimbatStation)).all()
        seismograms = session.exec(select(AimbatSeismogram)).all()
    ```

For the typical case of one waveform per station, the station and seismogram
counts for an event should match. A mismatch usually means the source data are
inconsistent: duplicate station entries with slightly different coordinates,
missing headers, or files that failed to parse. Worth investigating before
processing, since gaps or duplicates affect alignment quality.

## Removing data

The unit of deletion is the **seismogram**: the record that ties a data source to
a station and an event. Removing a seismogram severs that link and drops the data
source entry. Events and stations are shared metadata containers, left in place
even when no seismogram references them any more, since they may still be needed
or were added deliberately via JSON.

=== "CLI"

    ```bash
    aimbat seismogram delete <SEISMOGRAM_ID>   # one seismogram
    aimbat event delete <EVENT_ID>             # an event and all its seismograms
    aimbat station delete <STATION_ID>         # a station and all its seismograms, across events
    ```

=== "Shell"

    ```bash
    seismogram delete <SEISMOGRAM_ID>
    event delete <EVENT_ID>
    station delete <STATION_ID>
    ```

=== "TUI"

    Press `Enter` on a row in the **Live data** tab for the action menu, then
    **Delete seismogram** (`d`); events and stations delete the same way from
    the **Project** tab.

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.core import delete_event, delete_seismogram, delete_station
    from aimbat.db import engine

    with Session(engine) as session:
        delete_seismogram(session, seismogram_id)
        delete_event(session, event_id)
        delete_station(session, station_id)
    ```

!!! note "The file on disk is never touched"

    Deleting a seismogram removes the database record and its link to the
    waveform source only. The underlying file is never modified.
