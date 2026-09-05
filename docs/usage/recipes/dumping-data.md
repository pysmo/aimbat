### Dumping data

Every major entity, and several of its sub-resources, has a `dump` subcommand
that prints its table as JSON, for archiving or scripting:

```bash
aimbat event dump
aimbat event dump --alias   # camelCase field names
```

`data`, `event`, `station`, `seismogram`, and `snapshot` each have one, plus
`parameter dump` and `quality dump` variants where those sub-resources exist
(e.g. `aimbat event parameter dump`, `aimbat station quality dump`).

The equivalent core function follows `dump_<entity>_table`, e.g.
[`dump_event_table`][aimbat.core.dump_event_table]:

```python
from sqlmodel import Session
from aimbat.db import engine
from aimbat.core import dump_event_table

with Session(engine) as session:
    events = dump_event_table(session, by_alias=True)
```

`snapshot dump` is the one exception: it combines five related tables into a
single JSON object, cross-referenced by `snapshot_id`, rather than dumping
one table:

```python
from aimbat.core import (
    dump_event_parameter_snapshot_table,
    dump_event_quality_snapshot_table,
    dump_seismogram_parameter_snapshot_table,
    dump_seismogram_quality_snapshot_table,
    dump_snapshot_table,
)

with Session(engine) as session:
    data = {
        "snapshots": dump_snapshot_table(session),
        "event_parameters": dump_event_parameter_snapshot_table(session),
        "seismogram_parameters": dump_seismogram_parameter_snapshot_table(session),
        "event_quality": dump_event_quality_snapshot_table(session),
        "seismogram_quality": dump_seismogram_quality_snapshot_table(session),
    }
```

| Key | Contents | Always present |
| --- | --- | --- |
| `snapshots` | metadata (ID, time, comment, `automatic` flag, hash) | Yes |
| `event_parameters` | event parameter snapshots | Yes |
| `seismogram_parameters` | per-seismogram parameter snapshots | Yes |
| `event_quality` | event quality (MCCC RMSE) | Only if MCCC has run |
| `seismogram_quality` | per-seismogram quality (ICCS CC, MCCC metrics) | Only if quality metrics exist |

`aimbat snapshot dump` (CLI) and `snapshot dump` (shell) build the same object.
