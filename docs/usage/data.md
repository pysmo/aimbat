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

```bash
aimbat data add *.sac
```

The shell (bash, zsh, ...) expands the glob before AIMBAT runs, so this works at
a normal prompt but not inside `aimbat shell`. Import deduplicates, so the same
command is safe to re-run:

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

Standard shell patterns apply:

```bash
aimbat data add event1/*.sac           # one subdirectory
aimbat data add data/**/*.sac          # recursive (bash 4+ with globstar; zsh)
aimbat data add data/*/BHZ.sac         # vertical component only
aimbat data add data/II.*.BHZ.sac      # network filter
```

### How events are matched and de-duplicated

AIMBAT links a SAC file to an existing event only if its origin time is
**exactly** equal to that event's stored time, to the microsecond (the precision
AIMBAT stores timestamps at). Otherwise it does not reuse that event.

A new origin time that nearly, but not exactly, matches an existing event's time
is not silently turned into a second event. It is flagged as a possible
near-duplicate. How close counts as "near" is controlled by
`event_duplicate_tolerance` and `event_duplicate_raise_tolerance` (see
[Aimbat Defaults](defaults.md)):

- Within `event_duplicate_tolerance` (default {{ event_duplicate_tolerance }}),
  a real import raises an error; a `--dry-run` reports a warning. A gap this
  small is usually timestamp precision loss upstream, such as the classic v6 SAC
  header's 32-bit float `o` field not round-tripping identically across files,
  rather than a genuinely distinct event.
- Beyond that but within `event_duplicate_raise_tolerance` (default
  {{ event_duplicate_raise_tolerance }}), import always raises, even during
  `--dry-run`. A gap this size usually signals a real timing problem in the
  source data, worth investigating before import.
- Beyond `event_duplicate_raise_tolerance`, the new origin time is treated as a
  genuinely independent event, with no warning.

The check runs against every event AIMBAT already knows about when a file is
processed, including events created earlier in the same `data add` call.
Resolving a flag is always first-wins: re-run with `--use-event <ID>` to link
the new file to the existing event's stored time and location exactly as they
are. It never merges, averages, or recomputes from the new file.

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

### Previewing before import

`--dry-run` shows what would be added without touching the database:

```bash
aimbat data add --dry-run *.sac
```

It prints which stations, events, and seismograms would be newly created versus
already known, and shows any near-duplicate warnings a real run would raise. That
makes it worth running as routine practice before a new batch: catching a flagged
near-duplicate here means resolving it up front with `--use-event <ID>` rather
than hitting it partway through a real import, which aborts the whole batch and
rolls back everything already added in that call.

`--dry-run` only softens the outcome for gaps within the tighter
`event_duplicate_tolerance` band. A gap in the wider band still raises.

## Automatic snapshots

`data add` snapshots every event that receives at least one newly imported
seismogram, at the end of the command, whatever `--type` produced it. This gives
a baseline to roll back to before any processing begins. Re-running `data add` on
files already in the project creates no new snapshot, since nothing changed. Pass
`--no-snapshot` to skip it for one invocation:

```bash
aimbat data add --no-snapshot *.sac
```

See [Snapshots](snapshots.md) for working with snapshots generally.

## Missing event or station metadata

SAC files from some sources omit event or station headers. Add the metadata from
a JSON file first, then link the SAC files to the resulting record.

### Supplying a missing event

```bash
aimbat data add --type json_event event.json
aimbat data add --use-event <EVENT_ID> --type sac *.sac
```

`--use-event` accepts a full UUID or any unique prefix from `aimbat event list`.

### Supplying a missing station

```bash
aimbat data add --type json_station station.json
aimbat data add --use-station <STATION_ID> --type sac waveform.sac
```

### JSON format

JSON event and station files must match the structure of
[`AimbatEvent`][aimbat.models.AimbatEvent] and
[`AimbatStation`][aimbat.models.AimbatStation]. Use `aimbat event dump` or
`aimbat station dump` to export existing records as templates.

Records are identified by random UUIDs, so JSON exported from one AIMBAT project
imports into another with no risk of ID collisions.

## In the TUI

The TUI file picker adds one file at a time; it cannot select multiple files or a
directory. For anything more, use the CLI or shell.

Press `d` to open a data-type menu (SAC, JSON Event, JSON Station), then a file
picker filtered to the relevant extensions.

## Checking the import

```bash
aimbat data list              # data sources for the default event
aimbat data list --all-events # all data sources in the project
aimbat event list             # events extracted from imported files
aimbat station list           # stations extracted from imported files
aimbat seismogram list        # seismograms for the default event
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

```bash
aimbat seismogram delete <SEISMOGRAM_ID>   # one seismogram
aimbat event delete <EVENT_ID>             # an event and all its seismograms
aimbat station delete <STATION_ID>         # a station and all its seismograms, across events
```

In the TUI, press `Enter` on a row in the **Seismograms** tab for the action
menu; events and stations delete the same way from the **Project** tab.

!!! note "The file on disk is never touched"

    Deleting a seismogram removes the database record and its link to the
    waveform source only. The underlying file is never modified.
