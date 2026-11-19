# flake8: noqa: E402, F403
"""ORM classes mapping to AIMBAT database tables.

Each class in this module corresponds to a table in the SQLite project database
and is built on [SQLModel](https://sqlmodel.tiangolo.com), which combines
SQLAlchemy (for database access) with Pydantic (for validation).

The main classes and their relationships are:

- `AimbatEvent`: a seismic event.
- `AimbatPhase`: a phase of an event, the unit of processing.
- `AimbatStation`: a seismic recording station.
- `AimbatSeismogram`: links an `AimbatEvent` to an `AimbatStation` and holds
  the timing metadata (`begin_time`, `delta`). Waveform data are accessed via
  the associated `AimbatDataSource`.
- `AimbatDataSource`: identifies the logical source of the waveform data for a
  seismogram and its type (e.g. SAC).
- `AimbatPick`: an initial pick as read or entered, with its provenance.
- `AimbatPhaseParameters`: processing parameters shared across all
  seismograms of a phase (window bounds, bandpass filter settings, MCCC
  settings, etc.).
- `AimbatSeismogramParameters`: processing state of a seismogram for one
  phase (`flip`, `select`, `refined_pick`), with its initial pick.
- `AimbatSnapshot`: a point-in-time copy of the parameters of a phase and its
  seismograms via `AimbatPhaseParametersSnapshot` and
  `AimbatSeismogramParametersSnapshot`, enabling rollback and comparison.
- `AimbatPhaseQuality` and `AimbatSeismogramQuality`: live quality metrics
  updated during processing. `AimbatSeismogramQuality` stores the ICCS
  cross-correlation coefficient `iccs_cc` and the MCCC metrics of a
  seismogram for a phase. `AimbatPhaseQuality` stores the MCCC global RMSE.
- `AimbatPhaseQualitySnapshot` and `AimbatSeismogramQualitySnapshot`:
  point-in-time copies of quality metrics captured alongside parameter
  snapshots.
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
