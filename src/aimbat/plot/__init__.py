# flake8: noqa: E402, F403
"""Visualisation and interactive quality control for seismograms and alignment results.

This module provides tools for generating static plots of seismic data and alignment
stacks, as well as interactive interfaces for refining phase picks and time windows.
It integrates with matplotlib to support both automated reporting and manual
verification workflows.
"""

_internal_names = set(dir())

from ._iccs import *
from ._seismograms import *

__all__ = [s for s in dir() if not s.startswith("_") and s not in _internal_names]

del _internal_names
