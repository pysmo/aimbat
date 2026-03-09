# Adding Data

## How AIMBAT stores data

AIMBAT never modifies input files. When you add a data source, AIMBAT reads
the metadata it needs (event location, station coordinates, initial pick time)
and stores copies in the project database. After import, the original files
are only accessed to read waveform samples.

Before any record is written to the database, AIMBAT validates the data
extracted from each file — checking that required fields are present, that
values are within expected ranges, and that types are correct. If a file fails
validation, the entire import for that file is aborted and the database is left
unchanged. Other files in the same batch are still processed.

!!! warning "Files must remain accessible"
    AIMBAT stores the path to each data file at import time. If you move,
    rename, or delete a file after importing it, AIMBAT will no longer be
    able to read waveform data for the associated seismogram. Keep data files
    in a stable location, or update the path in the database before moving
    them.

---

## Data types

AIMBAT supports three data types, selected with `--type`:

| Type | Flag | What it provides |
|------|------|-----------------|
| SAC | `--type sac` *(default)* | Station + event + seismogram waveform |
| JSON event | `--type json_event` | Event metadata only — no seismogram created |
| JSON station | `--type json_station` | Station metadata only — no seismogram created |

SAC files are recognised by the extensions `.sac`, `.bhz`, `.bhn`, and `.bhe`.
JSON files use `.json` regardless of whether they carry event or station data,
so the `--type` flag is required to distinguish them.

---

## Adding SAC files

The most common case — a directory of SAC files for one or more events:

```bash
aimbat data add *.sac
```

Shell glob expansion is the primary way to select files. Because AIMBAT
deduplicates on import, you can safely re-run the same command — files already
in the project are skipped:

```bash
aimbat data add *.sac          # first run: imports everything
aimbat data add *.sac          # second run: no-op, all files already known
```

### Selecting subsets

Standard shell patterns apply:

```bash
aimbat data add event1/*.sac           # one subdirectory
aimbat data add data/**/*.sac          # recursive (bash 4+ with globstar)
aimbat data add data/*/BHZ.sac         # vertical component only
aimbat data add data/II.*.BHZ.sac      # network filter
```

### Previewing before import

Use `--dry-run` to see what would be added without touching the database:

```bash
aimbat data add --dry-run *.sac
```

### Initial picks

SAC files carry named time markers (`t0`–`t9`). AIMBAT reads one of these as
the initial phase pick (`t0` in AIMBAT's terminology). The default header is
`t0`; change it with `AIMBAT_SAC_PICK_HEADER`:

```bash
AIMBAT_SAC_PICK_HEADER=t1 aimbat data add *.sac
```

Or set it permanently for a project in `.env`:

```bash title=".env"
AIMBAT_SAC_PICK_HEADER=t1
```

---

## Mixing SAC and JSON

JSON files let you pre-populate event or station records independently of SAC
files — useful when SAC headers are incomplete or when you want to add
metadata first and link waveform files later.

### Supplying a missing event

If your SAC files do not carry event metadata (e.g. origin time or
coordinates), add it from a JSON file first, then link the SAC files to the
resulting event:

```bash
aimbat data add --type json_event event.json
aimbat data add --use-event <EVENT_ID> --type sac *.sac
```

`--use-event` accepts a full UUID or any unique prefix from `aimbat event list`.

### Supplying a missing station

Similarly, if a SAC file lacks station coordinates:

```bash
aimbat data add --type json_station station.json
aimbat data add --use-station <STATION_ID> --type sac waveform.sac
```

### JSON format

JSON event and station files must match the structure of
[`AimbatEvent`][aimbat.models.AimbatEvent] and
[`AimbatStation`][aimbat.models.AimbatStation] respectively. Use
`aimbat event dump` or `aimbat station dump` to export existing records as
templates.

Every record in AIMBAT is identified by a UUID rather than a simple integer.
This matters when importing JSON from another AIMBAT project: because UUIDs are
generated randomly from a very large space, there is no realistic chance of two
projects producing the same ID. JSON files exported from one project can be
imported into another without any risk of ID collisions.

---

## In the TUI and GUI

Both the TUI and GUI provide a basic file picker for adding SAC files. For
anything beyond a straightforward single-directory import — recursive globs,
mixed types, `--dry-run` checks, or JSON metadata — use the CLI or shell.

=== "TUI"

    Press `d` to open a data-type menu (SAC, JSON Event, JSON Station), then
    a file picker filtered to the relevant extensions.

=== "GUI"

    Use the **Add Data** button in the Project tab.

---

## Inspecting what was imported

```bash
aimbat data list              # data sources for the default event
aimbat data list --all-events # all data sources in the project
aimbat event list             # events extracted from imported files
aimbat station list           # stations extracted from imported files
aimbat seismogram list        # seismograms for the default event
```

After import, compare the station count and seismogram count for the event:

```bash
aimbat station list
aimbat seismogram list
```

In the typical case — one waveform per station — the two numbers should be
equal. A mismatch usually means something in the source data is inconsistent:
duplicate station entries with slightly different coordinates, missing headers,
or files that failed to parse cleanly. It is worth investigating before moving
on to processing, since unexpected duplicates or gaps in the dataset can affect
alignment quality.

---

## Removing data

The unit of deletion in AIMBAT is the **seismogram**. This reflects the data
model: a seismogram is the record that ties together a waveform file, a
station, and an event. Removing a seismogram severs that link and drops the
associated data source entry. Events and stations are metadata containers
shared across seismograms — they are left in place even if no seismograms
reference them any more, since they may still be needed (or may have been
added intentionally via JSON).

To remove a single seismogram:

```bash
aimbat seismogram delete <SEISMOGRAM_ID>
```

To remove everything belonging to an event — all its seismograms and the event
record itself:

```bash
aimbat event delete <EVENT_ID>
```

To remove all seismograms associated with a station (across all events) and
then the station record:

```bash
aimbat station delete <STATION_ID>
```

In the TUI, select any row in the **Seismograms** tab and press `Enter` to
open the action menu, which includes a delete option. Events and stations can
be deleted from the **Project** tab in the same way.

!!! note
    Deleting a seismogram from AIMBAT never touches the underlying file on
    disk — only the database record and its link to the waveform source are
    removed.
