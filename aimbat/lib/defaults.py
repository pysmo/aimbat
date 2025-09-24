"""Manage defaults used in an AIMBAT project."""

from dotenv import load_dotenv
import os

load_dotenv(".env")

_DEFAULTS_DICT = {
    "AIMBAT_PROJECT": (
        AIMBAT_PROJECT := os.getenv("AIMBAT_PROJECT", "aimbat.db"),
        "AIMBAT project file location.",
    ),
    "AIMBAT_DB_URL": (
        AIMBAT_DB_URL := os.getenv(
            "AIMBAT_DB_URL", rf"sqlite+pysqlite:///{AIMBAT_PROJECT}"
        ),
        "AIMBAT database url.",
    ),
    "AIMBAT_LOGFILE": (
        AIMBAT_LOGFILE := os.getenv("AIMBAT_LOGFILE", "aimbat.log"),
        "Log file location.",
    ),
    "AIMBAT_WINDOW_PRE": (
        AIMBAT_WINDOW_PRE := os.getenv("AIMBAT_WINDOW_PRE", -15.0),
        "Initial relative begin time of window.",
    ),
    "AIMBAT_WINDOW_POST": (
        AIMBAT_WINDOW_POST := os.getenv("AIMBAT_WINDOW_POST", 15),
        "Initial relative end time of window.",
    ),
    "AIMBAT_MIN_CCNORM": (
        AIMBAT_MIN_CCNORM := os.getenv("AIMBAT_MIN_CCNORM", 0.4),
        "Initial minimum cross correlation coefficient.",
    ),
    "AIMBAT_WINDOW_PADDING": (
        AIMBAT_WINDOW_PADDING := os.getenv("AIMBAT_WINDOW_PADDING", 20),
        "Padding around time window in seconds.",
    ),
    "AIMBAT_SAC_PICK_HEADER": (
        AIMBAT_SAC_PICK_HEADER := os.getenv("AIMBAT_SAC_PICK_HEADER", "t0"),
        "SAC header field where initial pick is stored.",
    ),
    "AIMBAT_SAMPLEDATA_SRC": (
        AIMBAT_SAMPLEDATA_SRC := os.getenv(
            "AIMBAT_SAMPLEDATA_SRC",
            "https://github.com/pysmo/data-example/archive/refs/heads/aimbat_v2.zip",
        ),
        "URL where sample data is downloaded from.",
    ),
    "AIMBAT_SAMPLEDATA_DIR": (
        AIMBAT_SAMPLEDATA_DIR := os.getenv("AIMBAT_SAMPLEDATA_DIR", "sample-data"),
        "Directory to store downloaded sample data.",
    ),
}


def print_defaults_table() -> None:
    """Print a pretty table with AIMBAT configuration options."""
    from aimbat.lib.common import logger
    from aimbat.lib.misc.rich_utils import make_table
    from rich.console import Console

    logger.info("Printing AIMBAT defaults table.")

    table = make_table(title="AIMBAT defaults")
    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Value", justify="center", style="magenta")
    table.add_column("Description", justify="left", style="green")

    for k, (v, d) in _DEFAULTS_DICT.items():
        table.add_row(k, str(v), d)

    console = Console()
    console.print(table)
