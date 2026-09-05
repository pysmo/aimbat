# API basics

The building blocks behind the AIMBAT interfaces (CLI, shell, TUI) are also
available for custom scripts and workflows.

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
    runs, snapshots. The CLI, shell, and TUI call the same functions, which
    commit internally.

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

Changes reach disk only on `session.commit()`, or when a core function commits
internally. An exception before that rolls the session back and discards the
changes.

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

Column fields (`event.time`, `station.network`, `seismogram.t0`, ...) are plain
Python attributes, read directly off any record a query returns.

A few frequently needed counts are precomputed as column properties, so reading
them costs nothing extra:

```python
event.seismogram_count      # seismograms belonging to this event
event.station_count         # distinct stations recording this event
station.seismogram_count    # seismograms recorded at this station
```

### Relationships

Relationships (`event.seismograms`, `seismogram.station`,
`seismogram.parameters`, ...) are attributes too, but the first access to one
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

Core functions commit internally. Querying and mutating models directly needs
both `add()` and `commit()`: a query result is already tracked by the session,
but a newly constructed object is not:

```python
with Session(engine) as session:
    event = session.exec(select(AimbatEvent)).first()
    event.latitude = 37.5   # already tracked by the session: no add() needed
    session.commit()        # required, or the change rolls back on exit

    new_event = AimbatEvent(time=..., latitude=..., longitude=...)
    session.add(new_event)  # required: not yet tracked by the session
    session.commit()
```

Each commit is a disk write. Calling a core function that commits internally,
such as [`set_seismogram_parameter`][aimbat.core.set_seismogram_parameter], once
per seismogram in a loop costs one commit per iteration. For changes across many
records, mutating them directly and committing once after the loop avoids that.
