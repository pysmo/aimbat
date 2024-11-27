"""Manage seismogram files in an AIMBAT project."""

from aimbat.lib.common import debug_callback, ic
from aimbat.lib.types import SeismogramFileType
from pathlib import Path
from typing import Annotated
import typer


def _add_files_to_project(
    seismogram_files: list[Path],
    filetype: SeismogramFileType,
    db_url: str | None,
    disable_progress_bar: bool = True,
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


app = typer.Typer(
    name="data",
    no_args_is_help=True,
    callback=debug_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)


@app.command("add")
def cli_add(
    ctx: typer.Context,
    files: Annotated[list[Path], typer.Argument(help="Seismogram files to be added.")],
    filetype: Annotated[
        SeismogramFileType, typer.Option(help="Specify type of seismogram file.")
    ] = SeismogramFileType.SAC,
) -> None:
    """Add or update data files in the AIMBAT project."""
    db_url = ctx.obj["DB_URL"]
    _add_files_to_project(
        seismogram_files=files,
        filetype=filetype.value,  # type: ignore
        db_url=db_url,
        disable_progress_bar=ic.enabled,
    )


@app.command("list")
def cli_list(
    ctx: typer.Context,
    all_events: Annotated[
        bool, typer.Option("--all", help="Select data for all events.")
    ] = False,
) -> None:
    """Print information on the data stored in AIMBAT."""
    db_url = ctx.obj["DB_URL"]
    _print_data_table(db_url, all_events)


if __name__ == "__main__":
    app()
