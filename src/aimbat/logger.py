"""Logging setup."""

from aimbat import settings
from loguru import logger


def configure_logging() -> None:
    """Reconfigure loguru sinks based on current settings."""
    logger.remove()
    logger.add(settings.logfile, rotation="100 MB", level=settings.log_level)


configure_logging()
