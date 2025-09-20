"""Common parameters for AIMBAT CLI."""

from aimbat.lib.common import logger, AIMBAT_LOGFILE
from aimbat.lib.db import AIMBAT_DB_URL
from dataclasses import dataclass
from cyclopts import Parameter


@Parameter(name="*")
@dataclass
class GlobalParameters:
    db_url: str = AIMBAT_DB_URL
    "Database connection URL."

    debug: bool = False
    "Run in debugging mode."

    use_qt: bool = False
    "Use pyqtgraph instead of matplotlib for plots (where applicable)."

    def __post_init__(self) -> None:
        if self.debug:
            logger.add(AIMBAT_LOGFILE, level="DEBUG")


@Parameter(name="*")
@dataclass
class TableParameters:
    format: bool = True
    "Format the output to be more human-readable."
