# API basics

The building blocks behind the AIMBAT interfaces (CLI, shell, TUI) are also
available for custom scripts and workflows, at two levels:

- **[`aimbat.actions`][aimbat.actions]: write your own workflows.** Each
  function does what one CLI command does and is saved when it returns. If it
  fails, nothing is changed. There is no session to manage.
- **[`aimbat.core`][aimbat.core]: get your hands dirty.** The functions the
  actions are built from. You open the session and decide when to commit, so
  several steps can share one transaction, and intermediate state can be
  inspected before anything is saved.

```python
from aimbat import actions
from aimbat.types import SeismogramParameter

run = actions.run_iccs(phase_id, autoflip=True, autoselect=True)
print(run.summary.message)

actions.set_seismogram_parameters(
    phase_id, bad_seismogram_ids, {SeismogramParameter.SELECT: False}
)
actions.create_snapshot(phase_id, comment="after ICCS")
```

Actions take record IDs and return plain values. Those that change several
records, such as `set_seismogram_parameters` or `delete_seismograms`, take a
list of IDs and save them all in one commit, so a script has no need to call
them in a loop. The rest of this page is about the second level.

Processing is done per phase, so the actions and core functions that process
data take the ID of a phase rather than of an event.
[`resolve_phase`][aimbat.core.resolve_phase] returns the phase of an event:

```python
from sqlmodel import Session
from aimbat.core import resolve_phase
from aimbat.db import engine

with Session(engine) as session:
    phase_id = resolve_phase(session, event_id).id
```

Without a name, `resolve_phase` returns the only phase of the event, and raises
`AmbiguousPhaseError` if the event has several.

!!! warning "Scripts written for earlier versions"

    Functions in `aimbat.core` used to commit their own changes. They no
    longer do. A script that calls a function that changes the project, such
    as `set_phase_parameter` or `create_snapshot`, must now call
    `session.commit()` before its session closes, or switch to the matching
    function in `aimbat.actions`.

## API components

The API has three primary parts:

1. **Session.** The working connection to the project database that every read
    or write goes through. It also defines the transaction boundary: changes
    become permanent only when the session commits.
2. **Models.** [SQLModel](https://sqlmodel.tiangolo.com) classes mirroring the
    database schema ([`aimbat.models`][]). The main ones are
    [`AimbatEvent`][aimbat.models.AimbatEvent],
    [`AimbatStation`][aimbat.models.AimbatStation], and
    [`AimbatSeismogram`][aimbat.models.AimbatSeismogram], plus their parameter
    and quality tables. Columns and relationships are plain attributes; sets of
    records come from [`select`][sqlalchemy.sql.expression.select] queries.
3. **Core functions.** High-level operations on those models
    ([`aimbat.core`][]): event selection, parameter changes, ICCS and MCCC
    runs, snapshots. None of them commits: each one makes its changes in the
    session it is given, and the caller commits.

## Starting a session

Every database operation needs a [`Session`][sqlalchemy.orm.Session]. It is
opened as a context manager so it is always closed cleanly:

```python
from sqlmodel import Session
from aimbat.db import engine

with Session(engine) as session:
    # query or modify data here
    pass
```

Changes reach disk only on `session.commit()`. An exception before that rolls
the session back and discards the changes.

[`aimbat.db.engine`][] reads `AIMBAT_PROJECT` (or the default `aimbat.db`)
exactly as the other interfaces do, so a script that imports it points at the
same database as the CLI. The [Project](project.md) page covers the
configuration options.

## Selecting events and stations

Given a record's ID, `Session.get` fetches it directly:

```python
from uuid import UUID
from sqlmodel import Session
from aimbat.db import engine
from aimbat.models import AimbatEvent

with Session(engine) as session:
    event = session.get(AimbatEvent, UUID("..."))
```

Queries by any other criterion use SQLModel's `select` with a `where` clause:

```python
--8<-- "docs/snippets/api_query.py"
```

`aimbat.core` also has cross-selections for the common cases:
[`get_stations_in_event`][aimbat.core.get_stations_in_event] and
[`get_events_using_station`][aimbat.core.get_events_using_station].

## Reading attributes

Column fields (`event.time`, `station.network`, `seismogram.begin_time`, ...)
are plain Python attributes, read directly off any record a query returns.

A few frequently needed counts are precomputed as column properties, so reading
them costs nothing extra:

```python
event.seismogram_count      # seismograms belonging to this event
event.station_count         # distinct stations recording this event
station.seismogram_count    # seismograms recorded at this station
```

### Relationships

Relationships (`event.seismograms`, `seismogram.station`,
`seismogram.phase_rows`, ...) are attributes too, but the first access to one
issues a query for the related records. That's cheap for a single record. Over a
large result set it becomes one query per row:

```python
with Session(engine) as session:
    seismograms = session.exec(select(AimbatSeismogram)).all()

    for seis in seismograms:
        print(seis.station.name)  # one SELECT per seismogram
```

Eager loading with SQLAlchemy's [`selectinload`][sqlalchemy.orm.selectinload]
fetches the related records for the whole result set in one extra query. The
[`rel`][aimbat.utils.rel] helper in [`aimbat.utils`][] casts a SQLModel
relationship attribute to the type `selectinload` expects:

```python
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from aimbat.db import engine
from aimbat.models import AimbatSeismogram
from aimbat.utils import rel

with Session(engine) as session:
    seismograms = session.exec(
        select(AimbatSeismogram).options(
            selectinload(rel(AimbatSeismogram.station)),
            selectinload(rel(AimbatSeismogram.event)),
        )
    ).all()

    for seis in seismograms:
        print(seis.station.name, seis.event.time)  # no further queries
```

## Committing changes

Neither core functions nor direct changes to models are saved until
`session.commit()`. Mutating models directly also needs `add()` for a new
object: a query result is already tracked by the session, but a newly
constructed object is not:

```python
with Session(engine) as session:
    event = session.exec(select(AimbatEvent)).first()
    event.latitude = 37.5   # already tracked by the session: no add() needed
    session.commit()        # required, or the change rolls back on exit

    new_event = AimbatEvent(time=..., latitude=..., longitude=...)
    session.add(new_event)  # required: not yet tracked by the session
    session.commit()
```

Each commit is a disk write, so commit once after a batch of changes, not once
per record. Core functions can be called in a loop and committed together
afterwards. Each call to an action commits on its own, which is why the actions
that change several records take a list.

## Working with seismogram data

The waveform samples for a seismogram are not a database column. They live in
the data source (the SAC or miniSEED file), and
[`AimbatSeismogram.data`][aimbat.models.AimbatSeismogram] reads and writes
them there.

```python
with Session(engine) as session:
    seis = session.exec(select(AimbatSeismogram)).first()

    samples = seis.data          # read-only NumPy array
    seis.data = samples * 2.0    # staged, not yet on disk
    session.commit()             # now written to the data source
```

Reading `data` returns a **read-only** array; `seis.data[0] = 1.0` raises.
Assigning `data` **stages** the write in the session, like any other model
change: it reaches the data source when the session commits and is discarded
if the session rolls back. Reads through the same session see the staged
value before the commit; other sessions see the old one until then.

AIMBAT itself never writes waveform samples — every processing step writes
parameters to the database. This matters only for custom scripts that replace
a seismogram's waveform.

!!! note "Embedding AIMBAT in a larger application"

    Importing `aimbat.models` (or `aimbat.db`, or any AIMBAT code that
    reads the project database) registers commit and rollback listeners on
    SQLAlchemy's `Session` class for the whole process, so that a staged
    `data` write is never silently lost. Every `Session` in the process,
    including those of unrelated libraries, then runs a short check on each
    commit and rollback; the work only happens for a session that actually
    staged a waveform write.
