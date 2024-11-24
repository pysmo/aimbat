"""Download or delete AIMBAT sample data.

The sampledata subcommand manages an example dataset that can be used
for testing or learning how to use AIMBAT.

The sample data source url can be viewed or changed via `aimbat default
<list/set> sampledata_src`. Likewise the sample data destination folder
be viewed or changed via `aimbat default <list/set> sampledata_dir`.
"""

from aimbat.lib.common import debug_callback
from typing import Annotated
import typer


def _delete_sampledata(db_url: str | None) -> None:
    from aimbat.lib.utils.sampledata import delete_sampledata
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        delete_sampledata(session)


def _download_sampledata(db_url: str | None, force: bool = False) -> None:
    from aimbat.lib.utils.sampledata import download_sampledata
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        download_sampledata(session, force)


app = typer.Typer(
    name="sampledata",
    no_args_is_help=True,
    callback=debug_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)


@app.command("download")
def sampledata_cli_download(
    ctx: typer.Context,
    force: Annotated[
        bool,
        typer.Option("--force", help="Delete the download directory and re-download"),
    ] = False,
) -> None:
    """Download aimbat sample data."""

    db_url = ctx.obj["DB_URL"]

    _download_sampledata(db_url, force)


@app.command("delete")
def sampledata_cli_delete(
    ctx: typer.Context,
) -> None:
    """Recursively delete sample data directory."""

    db_url = ctx.obj["DB_URL"]
    _delete_sampledata(db_url)


if __name__ == "__main__":
    app()
