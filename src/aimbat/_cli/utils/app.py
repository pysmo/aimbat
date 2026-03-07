"""
Utilities for AIMBAT.

The utils subcommand contains useful tools that
are not strictly part of an AIMBAT workflow.
"""

from cyclopts import App

from aimbat._config import cli_settings_list

from .sampledata import app as sampledata_app

app = App(name="utils", help=__doc__, help_format="markdown")
app.command(cli_settings_list, name="settings")
app.command(sampledata_app, name="sampledata")


if __name__ == "__main__":
    app()
