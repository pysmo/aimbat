"""AIMBAT (Automated and Interactive Measurement of Body wave Arrival Times).

A tool for measuring teleseismic body wave arrival times across large
seismic arrays. It uses ICCS (Iterative Cross-Correlation and Stack) to
refine phase arrival picks simultaneously across all seismograms, followed
by MCCC (Multi-Channel Cross-Correlation) for final relative arrival time
measurements. The workflow is controlled through a CLI, a terminal UI, or
directly via the Python API.
"""

from loguru import logger

from ._config import settings as settings

# Loguru's library idiom: a package that isn't the application emits nothing
# until someone asks for it. `aimbat.logger.configure_logging()`, called by
# the CLI and TUI entrypoints, enables these records again.
logger.disable("aimbat")

__all__ = ["settings"]

name = "aimbat"
