"""Logging configuration for AIMBAT using loguru.

Logging is controlled by two settings (see `aimbat._config`):

- `log_level`: minimum severity level to record. Valid levels from most to
  least verbose: `TRACE`, `DEBUG`, `INFO`, `SUCCESS`, `WARNING`,
  `ERROR`, `CRITICAL`. Defaults to `INFO`.
- `logfile`: path to the log file. Defaults to `aimbat.log` in the current
  working directory.

Both settings can be overridden per project via environment variable or a
`.env` file in the current working directory:

```bash
AIMBAT_LOG_LEVEL=DEBUG
AIMBAT_LOGFILE=/path/to/custom.log
```
"""

from aimbat import settings
from loguru import logger


def configure_logging() -> None:
    """Reconfigure loguru sinks based on current settings.

    Removes all existing loguru handlers and adds a single file sink using
    `Settings.logfile` and `Settings.log_level` from the active `aimbat.settings`
    instance. Log files are rotated at 100 MB.
    """
    logger.remove()
    logger.add(settings.logfile, rotation="100 MB", level=settings.log_level)


configure_logging()
