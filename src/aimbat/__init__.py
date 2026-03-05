"""
AIMBAT (Automated and Interactive Measurement of Body wave Arrival Times)
is a tool for measuring teleseismic body wave arrival times across large
seismic arrays. It uses ICCS (Iterative Cross-Correlation and Stack) to
refine phase arrival picks simultaneously across all seismograms, followed
by MCCC (Multi-Channel Cross-Correlation) for final relative arrival time
measurements. The workflow is controlled through a CLI, a terminal UI, or
directly via the Python API.
"""

from ._config import settings as settings

__all__ = ["settings"]

name = "aimbat"
