"""Common parameters for AIMBAT CLI."""

from dataclasses import dataclass
from cyclopts import Parameter
import aimbat.lib.common as common


@Parameter(name="*")
@dataclass
class GlobalParameters:
    debug: bool = False
    "Run in debugging mode."

    use_qt: bool = False
    "Use pyqtgraph instead of matplotlib for plots (where applicable)."

    def __post_init__(self) -> None:
        if self.debug:
            common.add_debug_logger()


@Parameter(name="*")
@dataclass
class TableParameters:
    format: bool = True
    "Format the output to be more human-readable."


@Parameter(name="*")
@dataclass
class IccsPlotParameters:
    pad: bool = True
    "Add extra padding to the time window for plotting."
    all: bool = False
    "Include all seismograms in the plot, even if not used in stack."
