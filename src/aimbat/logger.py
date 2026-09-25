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

Nothing is logged until `configure_logging()` runs, and only AIMBAT's own
entrypoints (the CLI, the TUI, and the `--debug` flag) call it. Importing
AIMBAT as a library therefore writes no log file and leaves the host
application's own loguru handlers alone. To turn AIMBAT's logging on from
library code:

```python
from aimbat.logger import configure_logging

configure_logging()
```

or, to route AIMBAT's records into handlers the host has already set up,
`loguru.logger.enable("aimbat")` instead.
"""

from pathlib import Path

from loguru import logger

from aimbat import settings


def configure_logging() -> None:
    """Reconfigure loguru sinks based on current settings.

    Removes all existing loguru handlers and adds a single file sink using
    `Settings.logfile` and `Settings.log_level` from the active `aimbat.settings`
    instance. Log files are rotated at 100 MB. `Settings.logfile`'s parent
    directory is created if it doesn't already exist. AIMBAT's own records,
    disabled on import of `aimbat`, are enabled again.

    Only call this from a process AIMBAT owns: the handlers it removes are
    every handler loguru holds, including any a host application registered.
    """
    Path(settings.logfile).parent.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(settings.logfile, rotation="100 MB", level=settings.log_level)
    logger.enable("aimbat")
