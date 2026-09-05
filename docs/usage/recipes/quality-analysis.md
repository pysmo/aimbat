### Quality analysis

Once alignment has run across many events, quality metrics accumulate on
`seismogram.quality` and `event.quality`: `iccs_cc` (correlation with the
ICCS stack, available as soon as the event has been opened), and, once MCCC
has run, `mccc_cc_mean` (mean pairwise correlation, a proxy for
signal-to-noise), `mccc_error` (formal timing standard error, `pd.Timedelta`),
and the event-level `mccc_rmse` (global array fit, `pd.Timedelta`). Querying
`AimbatSeismogram`, `AimbatStation`, and `AimbatEvent` records directly and
building a DataFrame from them supports aggregation and plotting with pandas
and matplotlib. See [Quality Assessment](../quality.md) for how to interpret
these values.

#### Build a per-seismogram DataFrame across all events

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

From here, the frame supports grouping by station, pivoting on event,
filtering by a quality threshold, or plotting directly with matplotlib.

#### Station-level quality summary

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

Each `stats` item exposes `cc_mean`, `mccc_cc_mean`, and `mccc_error` as (mean,
SEM) pairs aggregated across all events at that station.

#### Event-level quality summary

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

`mccc_rmse` on each stats object is the global array fit for that event,
useful for comparing event difficulty across a dataset.
