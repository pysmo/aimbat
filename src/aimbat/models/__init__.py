# flake8: noqa: E402, F403
"""ORM classes mapping to AIMBAT database tables.

Each class in this module corresponds to a table in the SQLite project database
and is built on [SQLModel](https://sqlmodel.tiangolo.com), which combines
SQLAlchemy (for database access) with Pydantic (for validation).

The main classes and their relationships are:

- `AimbatEvent` — a seismic event. Only one event can be the default at a time,
  enforced by a database constraint on the `is_default` column.
- `AimbatStation` — a seismic recording station.
- `AimbatSeismogram` — links an `AimbatEvent` to an `AimbatStation` and holds
  the timing metadata (`begin_time`, `delta`, `t0`). Waveform data is accessed
  via the associated `AimbatDataSource`.
- `AimbatDataSource` — records where the waveform data for a seismogram is
  stored, along with its type (e.g. SAC).
- `AimbatEventParameters` — processing parameters shared across all seismograms
  of an event (window bounds, bandpass filter settings, MCCC settings, etc.).
- `AimbatSeismogramParameters` — per-seismogram processing parameters
  (`flip`, `select`, working pick `t1`).
- `AimbatSnapshot` — captures a point-in-time copy of event and seismogram
  parameters via `AimbatEventParametersSnapshot` and
  `AimbatSeismogramParametersSnapshot`, enabling rollback and comparison.
- `AimbatEventQuality` / `AimbatSeismogramQuality` — live quality metrics updated
  during processing; `AimbatSeismogramQuality` stores the ICCS cross-correlation
  coefficient `iccs_cc` and MCCC per-seismogram metrics; `AimbatEventQuality`
  stores the MCCC global RMSE.
- `AimbatEventQualitySnapshot` / `AimbatSeismogramQualitySnapshot` — point-in-time
  copies of quality metrics captured alongside parameter snapshots.
"""

from .._utils import export_module_names

_internal_names = set(dir())

from ._models import *
from ._parameters import *
from ._quality import *
from ._readers import *

__all__ = [s for s in dir() if not s.startswith("_") and s not in _internal_names]

export_module_names(globals(), __name__)

del _internal_names
