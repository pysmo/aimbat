"""Common parameters for AIMBAT CLI."""

from aimbat.config import settings
from dataclasses import dataclass
from cyclopts import Parameter


@Parameter(name="*")
@dataclass
class GlobalParameters:
    debug: bool = False
    "Run in debugging mode."

    use_qt: bool = False
    "Use pyqtgraph instead of matplotlib for plots (where applicable)."

    def __post_init__(self) -> None:
        if self.debug:
            settings.debug = True


@Parameter(name="*")
@dataclass
class TableParameters:
    short: bool = True
    "Shorten UUIDs and format data."


@Parameter(name="*")
@dataclass
class IccsPlotParameters:
    pad: bool = True
    "Add extra padding to the time window for plotting."
    all: bool = False
    "Include all seismograms in the plot, even if not used in stack."
