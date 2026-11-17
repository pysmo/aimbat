# flake8: noqa: E402, F403
"""Complete user actions for scripted AIMBAT workflows.

Each function performs the equivalent of one CLI command, such as adding
data, changing parameters, running ICCS or MCCC, or creating a snapshot. Its
changes are saved before it returns. If it fails, the project is left
unchanged. No session handling is required.

Functions take record IDs and plain values, and return plain values.
Functions that modify several records, such as `set_seismogram_parameters`
or `delete_seismograms`, take a list of IDs and save all changes together.
The exception is `prepare_iccs`, which returns the ICCS instance itself for
use in interactive plots and custom processing.

Every function operates on the project AIMBAT is configured to use, unless a
different project database is given as `engine`.

Where several operations must share one transaction, or changes must be
inspected before they are saved, `aimbat.core` provides the necessary
control.
"""

from .._utils import export_module_names

_internal_names = set(dir())

from ._data import *
from ._event import *
from ._iccs import *
from ._note import *
from ._seismogram import *
from ._snapshot import *
from ._station import *

__all__ = [s for s in dir() if not s.startswith("_") and s not in _internal_names]

export_module_names(globals(), __name__)

del _internal_names
