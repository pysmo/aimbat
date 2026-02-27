# flake8: noqa: E402, F403
"""I/O interface for AIMBAT data sources.

Data source modules register their read/write and creation capabilities using
the `register_*` functions exported from this package. Not all data sources
need to support all capabilities — a source providing waveform data only would
register a reader and writer but not the creator functions.

The SAC data source (`aimbat.io._sac`) is included and registers its
capabilities automatically.
"""

from .._utils import export_module_names

_internal_names = set(dir())

from ._base import *
from ._sac import *

__all__ = [s for s in dir() if not s.startswith("_") and s not in _internal_names]

export_module_names(globals(), __name__)

del _internal_names
