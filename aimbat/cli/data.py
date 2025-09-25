"""Manage seismogram files in an AIMBAT project."""

from __future__ import annotations
from aimbat.cli.common import GlobalParameters, TableParameters
from aimbat.lib.io import DataType
from pathlib import Path
from cyclopts import App, Parameter, validators
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from collections.abc import Sequence


def _add_files_to_project(
    seismogram_files: Sequence[Path],
    filetype: DataType,
    show_progress_bar: bool,
) -> None:
    from aimbat.lib.data import add_files_to_project

    disable_progress_bar = not show_progress_bar

    add_files_to_project(
        seismogram_files,
        filetype,
        disable_progress_bar,
    )


def _print_data_table(format: bool, all_events: bool) -> None:
    from aimbat.lib.data import print_data_table

    print_data_table(format, all_events)


app = App(name="data", help=__doc__, help_format="markdown")


@app.command(name="add")
def cli_data_add(
    seismogram_files: Annotated[
        list[Path],
        Parameter(
            name="files", consume_multiple=True, validator=validators.Path(exists=True)
        ),
    ],
    *,
    filetype: DataType = DataType.SAC,
    show_progress_bar: Annotated[bool, Parameter(name="progress")] = True,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Add or update data files in the AIMBAT project.

    Parameters:
        seismogram_files: Seismogram files to be added.
        filetype: Specify type of seismogram file.
        show_progress_bar: Display progress bar.
    """

    global_parameters = global_parameters or GlobalParameters()

    _add_files_to_project(seismogram_files, filetype, show_progress_bar)


@app.command(name="list")
def cli_data_list(
    *,
    all_events: Annotated[bool, Parameter(name="all")] = False,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print information on the data stored in AIMBAT.

    Parameters:
        all_events: Select data for all events.
    """

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    _print_data_table(table_parameters.format, all_events)


if __name__ == "__main__":
    app()
