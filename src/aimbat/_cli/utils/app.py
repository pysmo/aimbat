"""Utilities for AIMBAT.

The utils subcommand contains useful tools that
are not strictly part of an AIMBAT workflow.
"""

from cyclopts import App

from aimbat._cli.common import handle_issues
from aimbat._config import cli_settings_list

from .completion import app as completion_app
from .lookup import cli_utils_lookup
from .sampledata import app as sampledata_app

app = App(name="utils", help=__doc__, help_format="markdown")
app.command(handle_issues(cli_settings_list), name="settings")
app.command(sampledata_app, name="sampledata")
app.command(completion_app, name="completion")
app.command(handle_issues(cli_utils_lookup), name="lookup")


if __name__ == "__main__":
    app()
