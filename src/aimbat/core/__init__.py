# flake8: noqa: E402, F403
"""Core logic for AIMBAT.

All functions take a SQLModel `Session` and work with the models in
`aimbat.models`. The main areas covered are:

- **Default event** — get and set the default event (`get_default_event`,
  `set_default_event`).
- **Data** — add data to the project, linking each source to its station,
  event, and seismogram records (`add_data_to_project`).
- **Events, seismograms, stations** — query, update, and delete records; read
  and write parameters.
- **ICCS / MCCC** — run the Iterative Cross-Correlation and Stack (`run_iccs`)
  and Multi-Channel Cross-Correlation (`run_mccc`) algorithms; update picks,
  time windows, and correlation thresholds.
- **Snapshots** — save, restore, and delete parameter snapshots
  (`create_snapshot`, `rollback_to_snapshot`).
- **Project** — create and delete the project database (`create_project`,
  `delete_project`).
"""

from .._utils import export_module_names

_internal_names = set(dir())

from ._data import *
from ._default_event import *
from ._event import *
from ._iccs import *
from ._project import *
from ._seismogram import *
from ._snapshot import *
from ._station import *

__all__ = [s for s in dir() if not s.startswith("_") and s not in _internal_names]

export_module_names(globals(), __name__)

del _internal_names
