# flake8: noqa: E402, F403
"""Business logic for AIMBAT processing operations.

All functions accept a SQLModel `Session` and operate on the ORM models in
`aimbat.models`. The main areas of functionality are:

- **Active event** — get and set the active event (`get_active_event`,
  `set_active_event`). Only one event is processed at a time; switching clears
  the seismogram data cache.
- **Data ingestion** — add data sources to the project, linking each to its
  station, event, and seismogram records (`add_data_to_project`).
- **Events, seismograms, stations** — query, update, and delete records; read
  and write processing parameters.
- **ICCS / MCCC** — run the Iterative Cross-Correlation and Stack (`run_iccs`)
  and Multi-Channel Cross-Correlation (`run_mccc`) algorithms; update picks,
  time windows, and correlation thresholds.
- **Snapshots** — create, restore, and delete parameter snapshots for rollback
  and comparison (`create_snapshot`, `rollback_to_snapshot`).
- **Project** — create and delete the project database (`create_project`,
  `delete_project`).
"""

from .._utils import export_module_names

_internal_names = set(dir())

from ._active_event import *
from ._data import *
from ._event import *
from ._iccs import *
from ._project import *
from ._seismogram import *
from ._snapshot import *
from ._station import *

__all__ = [s for s in dir() if not s.startswith("_") and s not in _internal_names]

export_module_names(globals(), __name__)

del _internal_names
