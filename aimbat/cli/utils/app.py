"""
Utilities for AIMBAT.

The utils subcommand contains useful tools that
are not strictly part of an AIMBAT workflow.
"""

from aimbat.cli.common import GlobalParameters
from aimbat.cli.utils.sampledata import app as sampledata_app
from pathlib import Path
from typing import Annotated
from cyclopts import App, Parameter


def _run_checks(sacfiles: list[Path]) -> None:
    from aimbat.lib.utils.checkdata import run_checks

    run_checks(sacfiles)


app = App(name="utils", help=__doc__, help_format="markdown")
app.command(sampledata_app, name="sampledata")


@app.command(name="checkdata")
def checkdata_cli(
    sacfiles: Annotated[list[Path], Parameter(name="data", consume_multiple=True)],
    *,
    common: GlobalParameters | None = None,
) -> None:
    """Check if there are any problems with SAC files before adding them to a project.

    Parameters:
        sacfiles: One or more SAC files.
    """

    common = common or GlobalParameters()

    _run_checks(sacfiles)


if __name__ == "__main__":
    app()
