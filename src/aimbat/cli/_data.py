"""Manage seismogram files in an AIMBAT project."""

from ._common import GlobalParameters, TableParameters, simple_exception
from aimbat.aimbat_types import DataType
from sqlmodel import Session
from cyclopts import App, Parameter, validators
from pathlib import Path
from typing import Annotated

app = App(name="data", help=__doc__, help_format="markdown")


@app.command(name="add")
@simple_exception
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

    Args:
        seismogram_files: Seismogram files to be added.
        filetype: Specify type of seismogram file.
        show_progress_bar: Display progress bar.
    """
    from aimbat.db import engine
    from aimbat.core import add_files_to_project

    global_parameters = global_parameters or GlobalParameters()

    disable_progress_bar = not show_progress_bar

    with Session(engine) as session:
        add_files_to_project(
            session,
            seismogram_files,
            filetype,
            disable_progress_bar,
        )


@app.command(name="list")
@simple_exception
def cli_data_list(
    *,
    all_events: Annotated[bool, Parameter(name="all")] = False,
    table_parameters: TableParameters | None = None,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Print information on the data stored in AIMBAT.

    Args:
        all_events: Select data for all events.
    """
    from aimbat.db import engine
    from aimbat.core import print_data_table

    table_parameters = table_parameters or TableParameters()
    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_data_table(session, table_parameters.short, all_events)


@app.command(name="dump")
@simple_exception
def cli_data_dump(
    *,
    global_parameters: GlobalParameters | None = None,
) -> None:
    """Dump the contents of the AIMBAT data table to json."""
    from aimbat.db import engine
    from aimbat.core import dump_data_table_to_json
    from rich import print_json

    global_parameters = global_parameters or GlobalParameters()

    with Session(engine) as session:
        print_json(dump_data_table_to_json(session))


if __name__ == "__main__":
    app()
