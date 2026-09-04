# flake8: noqa: E402, F403
#
"""File I/O for AIMBAT.

Data source modules plug in by decorating their functions with the decorator
factories from this package (`station_creator`, `event_creator`,
`seismogram_creator`, `seismogram_data_reader`, `seismogram_data_writer`).
Not every source needs to implement everything. A source that only provides
waveform data would register a reader and writer but skip the creator
functions.

SAC (`aimbat.io.sac`), JSON (`aimbat.io.json`), and miniSEED
(`aimbat.io.mseed`) data sources are loaded automatically and their
capabilities registered on import of this package.
"""

from .._utils import export_module_names

_internal_names = set(dir())

from . import json as json
from . import mseed as mseed
from . import sac as sac
from ._base import *
from ._data import *

__all__ = [s for s in dir() if not s.startswith("_") and s not in _internal_names]

export_module_names(globals(), __name__)

del _internal_names
