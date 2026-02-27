# flake8: noqa: E402, F403
#
"""File I/O for AIMBAT.

Data source modules plug in by calling the `register_*` functions from this
package. Not every source needs to implement everything — a source that only
provides waveform data would register a reader and writer but skip the creator
functions.

SAC (`aimbat.io.sac`) and JSON (`aimbat.io.json`) data sources are loaded
automatically and their capabilities registered on import of this package.
"""

from .._utils import export_module_names

_internal_names = set(dir())

from ._data import *
from ._base import *
from . import sac as sac, json as json

__all__ = [s for s in dir() if not s.startswith("_") and s not in _internal_names]

export_module_names(globals(), __name__)

del _internal_names
