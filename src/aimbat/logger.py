"""Logging setup."""

from loguru import logger
from aimbat.config import settings

logger.remove(0)
_ = logger.add(settings.logfile, rotation="100 MB", level="INFO")

if settings.debug:
    logger.add(settings.logfile, level="DEBUG")
