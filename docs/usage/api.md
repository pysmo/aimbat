# Python API

The CLI, shell, TUI, and GUI all use the same underlying Python library. You
can use it directly for custom scripts, automation, or workflows that go beyond
what the other interfaces expose. See the full [API reference](../api/aimbat.md)
for a complete listing.

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
