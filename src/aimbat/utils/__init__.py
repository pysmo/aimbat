# flake8: noqa: E402, F403
"""Miscellaneous helpers for AIMBAT.

Covers five areas:

- **Maths** — mean/SEM over numeric and `pd.Timedelta` values
  (`mean_and_sem`, `mean_and_sem_timedelta`).
- **Errors** — exception message plus attached notes, for display
  (`exception_message`).
- **Pydantic** — validation-error formatting, title-map lookup, and the
  serialisation shared by the `core.dump_*_table` functions
  (`format_validation_error`, `get_title_map`, `dump_models`).
- **Sample data** — download and delete the bundled sample dataset
  (`download_sampledata`, `delete_sampledata`).
- **UUIDs / formatting** — short-UUID lookup, `rel()` for typed
  relationships, and the `fmt_*` display formatters (`utils.formatters`).
"""

from .._utils import export_module_names

_internal_names = set(dir())

from ._errors import *
from ._maths import *
from ._pydantic import *
from ._sampledata import *
from ._sqlalchemy import *
from ._uuid import *

__all__ = [s for s in dir() if not s.startswith("_") and s not in _internal_names]

export_module_names(globals(), __name__)

del _internal_names
