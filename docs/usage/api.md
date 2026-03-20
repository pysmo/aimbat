# Python API

After running ICCS and MCCC alignment across many events, the accumulated
quality metrics span stations and events in ways that are natural to analyse
with pandas and matplotlib but impossible from the CLI or TUI. The Python API
is the primary interface for that kind of post-processing quality analysis: you
query `AimbatSeismogram`, `AimbatStation`, and `AimbatEvent` records directly,
build DataFrames, and apply whatever aggregation or visualisation you need.

The same API also drives the CLI and TUI internally, so it covers the full
workflow — data ingestion, parameter management, alignment, snapshots — not
just quality analysis. See the full [API reference](../api/aimbat.md) for a
complete listing.

!!! note "Writing seismogram data"
    [`AimbatSeismogram.data`][aimbat.models.AimbatSeismogram.data] is backed by
    an IO cache. Assigning a new array replaces the cached value and, for data
    types that support it, writes through to the source file on disk. In-place
    mutation of the returned array does not persist — each access returns the
    cached value, so changes to the array itself are silently discarded:

    ```python
    seis.data = my_modified_array  # replaces cache (and writes to disk if supported)
    arr = seis.data
    arr[0] = 42                    # raises ValueError — the cached array is read-only
    ```

    AIMBAT does not write seismogram data in normal usage. All processing results
    are stored as parameters in the database; source files are treated as
    read-only.

## Core Concepts

The API is built on three main components:

1. **Models**: [SQLModel](https://sqlmodel.tiangolo.com) classes that represent
    the database schema (`aimbat.models`) as Python objects.
2. **Core Functions**: High-level operations that manipulate those models
    (`aimbat.core`).
3. **Database Session**: A SQLAlchemy session used to track changes and
    interact with the project database.

## Project Location

By default AIMBAT reads and writes `aimbat.db` in the current directory. Set
`AIMBAT_PROJECT` to use a different path:

```bash
export AIMBAT_PROJECT=/path/to/my/project.db
```

The `aimbat.db.engine` singleton picks this up automatically, so scripts that
import it will use the same database as the CLI.

## Session Management

Every database operation requires a `Session`. Use it as a context manager so
it is always closed cleanly:

```python
from sqlmodel import Session
from aimbat.db import engine

with Session(engine) as session:
    # query or modify data here
    pass
```

Changes accumulate in the session and are written to disk only when
`session.commit()` is called (or when you call a core function that commits
internally). If an exception is raised before committing, the session is rolled
back automatically.

## Creating a Project

```python
from aimbat.db import engine
from aimbat.core import create_project

create_project(engine)
```

This is a one-time operation that creates the schema and the SQLite triggers
that enforce database constraints and track modification times.
It raises `RuntimeError` if the schema already exists.

## Adding Data

The central function is `add_data_to_project`:

```python
from sqlmodel import Session
from aimbat.db import engine
from aimbat.core import add_data_to_project
from aimbat.io import DataType

with Session(engine) as session:
    add_data_to_project(session, paths, DataType.SAC)
```

The `DataType` enum controls what is read from each source:

| `DataType`       | What is created                          |
|------------------|------------------------------------------|
| `SAC`            | Event + Station + Seismogram             |
| `JSON_EVENT`     | Event only (no seismogram)               |
| `JSON_STATION`   | Station only (no seismogram)             |

### JSON formats

**Event** (`DataType.JSON_EVENT`):

```json
{
    "time": "2024-03-15T14:22:11Z",
    "latitude": 37.5,
    "longitude": 143.0,
    "depth": 35.0
}
```

**Station** (`DataType.JSON_STATION`):

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

### Providing event or station metadata externally

SAC files from some sources omit event or station headers. In that case, add
the metadata separately first and then link the SAC files to the resulting
database records using `event_id` and `station_id`:

```python
with Session(engine) as session:
    add_data_to_project(session, [event_json], DataType.JSON_EVENT)
    add_data_to_project(session, [station_json], DataType.JSON_STATION)

    event = session.exec(select(AimbatEvent)).one()
    station = session.exec(select(AimbatStation)).one()

    add_data_to_project(
        session,
        sac_files,
        DataType.SAC,
        event_id=event.id,
        station_id=station.id,
    )
```

## Quality Analysis

After alignment has been run across a set of events, each seismogram carries
quality metrics that can be queried directly from the database. The sections
below show the most common patterns.

### Quality data model

Per-seismogram metrics are stored in `AimbatSeismogramQuality` and accessed via
`seismogram.quality`:

| Attribute | Description |
|---|---|
| `iccs_cc` | ICCS cross-correlation with the stack |
| `mccc_cc_mean` | MCCC waveform quality — mean CC across seismogram pairs |
| `mccc_cc_std` | MCCC waveform consistency — std of CC across pairs |
| `mccc_error` | MCCC timing precision (`pd.Timedelta`, SEM from covariance matrix) |

The per-event MCCC global array fit is stored in `AimbatEventQuality` and
accessed via `event.quality`:

| Attribute | Description |
|---|---|
| `mccc_rmse` | Global array fit (`pd.Timedelta`) |

### Build a per-seismogram DataFrame across all events

The most flexible starting point is a flat DataFrame with one row per
seismogram:

```python
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select
import pandas as pd

from aimbat.db import engine
from aimbat.models import AimbatSeismogram
from aimbat.utils import rel

with Session(engine) as session:
    seismograms = session.exec(
        select(AimbatSeismogram).options(
            selectinload(rel(AimbatSeismogram.station)),
            selectinload(rel(AimbatSeismogram.event)),
            selectinload(rel(AimbatSeismogram.quality)),
        )
    ).all()

    rows = []
    for seis in seismograms:
        q = seis.quality
        rows.append({
            "station": f"{seis.station.network}.{seis.station.name}",
            "event_time": seis.event.time,
            "iccs_cc": q.iccs_cc if q else None,
            "mccc_cc_mean": q.mccc_cc_mean if q else None,
            "mccc_error_s": q.mccc_error.total_seconds() if (q and q.mccc_error) else None,
        })

df = pd.DataFrame(rows)
```

From here you can groupby station, pivot on event, filter by quality threshold,
or feed the result directly into matplotlib.

### Station-level quality summary

`SeismogramQualityStats.from_station` aggregates all per-seismogram metrics
across every event recorded at a station:

```python
from aimbat.models import AimbatSeismogram, AimbatStation, SeismogramQualityStats

with Session(engine) as session:
    stations = session.exec(
        select(AimbatStation).options(
            selectinload(rel(AimbatStation.seismograms)).selectinload(
                rel(AimbatSeismogram.quality)
            )
        )
    ).all()
    stats = [SeismogramQualityStats.from_station(s) for s in stations]
```

Each `stats` item exposes `cc_mean`, `mccc_cc_mean`, and `mccc_error` as
(mean, SEM) pairs aggregated across all events at that station.

### Event-level quality summary

`SeismogramQualityStats.from_event` aggregates per-seismogram metrics for a
single event and also carries the global `mccc_rmse` array-fit value:

```python
from aimbat.models import AimbatEvent, AimbatSeismogram, SeismogramQualityStats

with Session(engine) as session:
    events = session.exec(
        select(AimbatEvent).options(
            selectinload(rel(AimbatEvent.seismograms)).selectinload(
                rel(AimbatSeismogram.quality)
            ),
            selectinload(rel(AimbatEvent.quality)),
        )
    ).all()
    stats = [SeismogramQualityStats.from_event(e) for e in events]
```

`mccc_rmse` on each stats object is the global array fit for that event —
useful for comparing event difficulty across a dataset.

## Worked Example

The script below builds a complete project from scratch. It loads **3 events**,
**10 stations**, and **20 seismograms** where the SAC files carry waveform data
but no event or station headers — all metadata is provided via JSON — and takes
an initial snapshot of each event before any processing.

```python
--8<-- "docs/snippets/api_load_project.py"
```

## Querying the Database

Models can be queried directly using SQLModel's `select`:

```python
--8<-- "docs/snippets/api_query.py"
```

## Deduplicating Events

`add_data_to_project` deduplicates stations automatically by SEED code
`(network, name, location, channel)`, so importing the same station from
multiple sources never creates duplicate records.

Events are a different story: they are deduplicated by exact origin time.
When two data sources report the same earthquake with times that differ by a
second or two, they are stored as separate `AimbatEvent` records. The script
below detects such near-duplicates, merges their seismograms into the record
with the most data, averages the location and depth, and removes the extras.

```python
--8<-- "docs/snippets/api_deduplicate.py"
```

## Running Alignment

```python
--8<-- "docs/snippets/api_alignment.py"
```
