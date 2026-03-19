from .align import app as align
from .data import app as data
from .event import app as event
from .pick import app as pick
from .plot import app as plot
from .project import app as project
from .seismogram import app as seismogram
from .shell import app as shell
from .snapshot import app as snapshot
from .station import app as station
from .utils import app as utils

__all__ = [
    "utils",
    "align",
    "data",
    "event",
    "pick",
    "plot",
    "project",
    "seismogram",
    "shell",
    "snapshot",
    "station",
]
