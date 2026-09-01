"""
AIMBAT
======

AIMBAT (Automated and Interactive Measurement of Body wave Arrival Times)
is an open-source software package for efficiently measuring teleseismic
body wave arrival times for large seismic arrays (Lou et al., 2012). It is
based on a widely used method called MCCC (Multi-Channel Cross-Correlation)
developed by VanDecar and Crosson (1990). The package is automated in the
sense of initially aligning seismograms for MCCC which is achieved by an
ICCS (Iterative Cross Correlation and Stack) algorithm. Meanwhile, a
graphical user interface is built to perform seismogram quality control
interactively. Therefore, user processing time is reduced while valuable
input from a user\'s expertise is retained. As a byproduct, SAC (Goldstein
et al., 2003) plotting and phase picking functionalities are replicated
and enhanced.

"""

import sys
import warnings

name = "aimbat"

_MIGRATION_NOTICE = (
    "pysmo.aimbat is the legacy AIMBAT 1 line and is no longer actively "
    "developed. It has been superseded by AIMBAT 2, which is distributed as "
    "'aimbat' (pip install aimbat) and imported as 'aimbat', no longer under "
    "the pysmo namespace. See https://github.com/pysmo/aimbat."
)

warnings.warn(_MIGRATION_NOTICE, DeprecationWarning, stacklevel=2)

_cli_notice_shown = False


def cli_deprecation_notice():
    """Print the AIMBAT 1 migration notice to stderr, once per process.

    Called by the console-script entry points, where a DeprecationWarning
    would otherwise be hidden by Python's default warning filters.
    """
    global _cli_notice_shown
    if not _cli_notice_shown:
        print("WARNING: " + _MIGRATION_NOTICE, file=sys.stderr)
        _cli_notice_shown = True
