from .align import app as align
from .data import app as data
from .event import app as event
from .plot import app as plot
from .project import app as project
from .seismogram import app as seismogram
from .shell import app as shell
from .snapshot import app as snapshot
from .station import app as station
from .tool import app as tool
from .tui import app as tui
from .utils import app as utils

__all__ = [
    "utils",
    "align",
    "data",
    "event",
    "tool",
    "plot",
    "project",
    "seismogram",
    "shell",
    "snapshot",
    "station",
    "tui",
]
