# flake8: noqa: E402, F403
"""Building blocks of `aimbat.actions` and the AIMBAT interfaces.

The functions in this module give finer control than `aimbat.actions`. They
allow several operations to share one transaction, and changes to be
inspected before they are saved.

Every function takes a session and operates on the records in
`aimbat.models`. Changes remain in the session until it is committed, and a
rollback discards them.

The functions cover the following areas:

- **Data**: adding data to the project (`add_data_to_project`), with each
  data source linked to its station, event and seismogram records.
- **Events, seismograms and stations**: retrieving, modifying and deleting
  records, and reading or setting their parameters.
- **Alignment**: ICCS (`run_iccs`) and MCCC (`run_mccc`) runs, and the
  setting of picks, time windows and the CC threshold.
- **Snapshots**: creating, restoring and deleting parameter snapshots
  (`create_snapshot`, `rollback_to_snapshot`).
- **Quality values**: checking whether stored quality values still match the
  current parameters (`Validity`).
- **Projects**: creating and deleting a project (`create_project`,
  `delete_project`), and upgrading a project created by an earlier version
  of AIMBAT (`upgrade_project`).
"""

from .._utils import export_module_names

_internal_names = set(dir())

from ._data import *
from ._event import *
from ._iccs import *
from ._migrations import *
from ._note import *
from ._project import *
from ._prune import *
from ._seismogram import *
from ._snapshot import *
from ._station import *
from ._validity import Validity as Validity

__all__ = [s for s in dir() if not s.startswith("_") and s not in _internal_names]

export_module_names(globals(), __name__)

del _internal_names
