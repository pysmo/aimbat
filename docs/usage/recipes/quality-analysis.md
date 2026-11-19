### Quality analysis

Once alignment has run across many events, quality metrics accumulate on the
quality records of each seismogram's rows (`row.quality`, with `row` from
`seismogram.phase_rows`) and of each phase (`phase.quality`): `iccs_cc`
(correlation with the ICCS stack, available as soon as the event has been
opened), and, once MCCC has run, `mccc_cc_mean` (mean pairwise correlation, a
proxy for signal-to-noise), `mccc_error` (formal timing standard error,
`pd.Timedelta`), and the phase-level `mccc_rmse` (global array fit,
`pd.Timedelta`). Querying
`AimbatSeismogram`, `AimbatStation`, and `AimbatEvent` records directly and
building a DataFrame from them supports aggregation and plotting with pandas
and matplotlib. See [Quality Assessment](../quality.md) for how to interpret
these values.

A stored value stays in the database after a parameter it was computed from
changes, but it no longer applies. `Validity` tells you which values still
match the current parameters. Build it once per session, after any changes,
and use it to skip the values that do not.

#### Build a per-seismogram DataFrame across all events

The most flexible starting point is a flat DataFrame with one row per
seismogram and phase:

```python
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select
import pandas as pd

from aimbat.core import Validity
from aimbat.db import engine
from aimbat.models import AimbatSeismogram, AimbatSeismogramParameters
from aimbat.utils import rel

with Session(engine) as session:
    validity = Validity.read(session)
    seismogram = selectinload(rel(AimbatSeismogramParameters.seismogram))
    phase_rows = session.exec(
        select(AimbatSeismogramParameters).options(
            seismogram.selectinload(rel(AimbatSeismogram.station)),
            seismogram.selectinload(rel(AimbatSeismogram.event)),
            selectinload(rel(AimbatSeismogramParameters.phase)),
            selectinload(rel(AimbatSeismogramParameters.quality)),
        )
    ).all()

    rows = []
    for row in phase_rows:
        seis, q = row.seismogram, row.quality
        iccs_ok = q is not None and validity.iccs_cc(row.id)
        mccc_ok = q is not None and validity.mccc(row.phase_id)
        rows.append({
            "station": f"{seis.station.network}.{seis.station.name}",
            "event_time": seis.event.time,
            "phase": row.phase.name,
            "iccs_cc": q.iccs_cc if iccs_ok else None,
            "mccc_cc_mean": q.mccc_cc_mean if mccc_ok else None,
            "mccc_error_s": q.mccc_error.total_seconds() if (mccc_ok and q.mccc_error) else None,
        })

df = pd.DataFrame(rows)
```

From here, the frame supports grouping by station, pivoting on event,
filtering by a quality threshold, or plotting directly with matplotlib.

#### Station-level quality summary

`SeismogramQualityStats.from_station` aggregates all per-seismogram metrics
across every event recorded at a station, leaving out values that no longer
apply:

```python
from aimbat.models import AimbatStation, SeismogramQualityStats

with Session(engine) as session:
    validity = Validity.read(session)
    stations = session.exec(
        select(AimbatStation).options(
            selectinload(rel(AimbatStation.seismograms))
            .selectinload(rel(AimbatSeismogram.phase_rows))
            .selectinload(rel(AimbatSeismogramParameters.quality))
        )
    ).all()
    stats = [SeismogramQualityStats.from_station(s, validity) for s in stations]
```

Each `stats` item exposes `cc_mean`, `mccc_cc_mean`, and `mccc_error` as (mean,
SEM) pairs aggregated across all events at that station.

#### Phase-level quality summary

`SeismogramQualityStats.from_phase` aggregates per-seismogram metrics for a
single phase of an event and also carries the global `mccc_rmse` array-fit
value:

```python
from aimbat.models import AimbatPhase, SeismogramQualityStats

with Session(engine) as session:
    validity = Validity.read(session)
    phases = session.exec(
        select(AimbatPhase).options(
            selectinload(rel(AimbatPhase.quality)),
            selectinload(rel(AimbatPhase.seismogram_parameters)).selectinload(
                rel(AimbatSeismogramParameters.quality)
            ),
        )
    ).all()
    stats = [SeismogramQualityStats.from_phase(p, validity) for p in phases]
```

`mccc_rmse` on each stats object is the global array fit for that phase,
useful for comparing event difficulty across a dataset.
[`dump_phase_quality_table`][aimbat.core.dump_phase_quality_table] returns
the same statistics as a list of dicts.
