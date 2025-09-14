"""Manage seismogram files in an AIMBAT project."""

from aimbat.cli.common import CommonParameters
from aimbat.lib.typing import SeismogramFileType
from pathlib import Path
from cyclopts import App, Parameter
from typing import Annotated


def _add_files_to_project(
    seismogram_files: list[Path],
    filetype: SeismogramFileType,
    db_url: str | None,
    disable_progress_bar: bool = False,
) -> None:
    from aimbat.lib.data import add_files_to_project
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        add_files_to_project(
            session,
            seismogram_files,
            filetype,
            disable_progress_bar=disable_progress_bar,
        )


def _print_data_table(db_url: str | None, all_events: bool) -> None:
    from aimbat.lib.data import print_data_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_data_table(session, all_events)


app = App(name="data", help=__doc__, help_format="markdown")


@app.command(name="add")
def cli_data_add(
    seismogram_files: Annotated[
        list[Path], Parameter(name="files", consume_multiple=True)
    ],
    *,
    filetype: SeismogramFileType = SeismogramFileType.SAC,
    common: CommonParameters | None = None,
) -> None:
    """Add or update data files in the AIMBAT project.

    Parameters:
        seismogram_files: Seismogram files to be added.
        filetype: Specify type of seismogram file.
    """

    common = common or CommonParameters()

    _add_files_to_project(
        seismogram_files=seismogram_files,
        filetype=filetype,
        db_url=common.db_url,
    )


@app.command(name="list")
def cli_data_list(
    *,
    all_events: Annotated[bool, Parameter(name="all")] = False,
    common: CommonParameters | None = None,
) -> None:
    """Print information on the data stored in AIMBAT.

    Parameters:
        all_events: Select data for all events.
    """

    common = common or CommonParameters()

    _print_data_table(common.db_url, all_events)


if __name__ == "__main__":
    app()
