"""Download or delete AIMBAT sample data.

The sampledata subcommand manages an example dataset that can be used
for testing or learning how to use AIMBAT.

The sample data source url can be viewed or changed via `aimbat default
<list/set> sampledata_src`. Likewise the sample data destination folder
be viewed or changed via `aimbat default <list/set> sampledata_dir`.
"""

from aimbat.cli.common import CommonParameters
from cyclopts import App


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


app = App(name="sampledata", help=__doc__, help_format="markdown")


@app.command(name="download")
def sampledata_cli_download(
    *, force: bool = False, common: CommonParameters | None = None
) -> None:
    """Download AIMBAT sample data.

    Downloads an example dataset to the directory specified in the
    `sampledata_dir` AIMBAT default variable.

    Parameters:
        force: Delete the download directory and re-download."
    """

    common = common or CommonParameters()

    _download_sampledata(common.db_url, force)


@app.command(name="delete")
def sampledata_cli_delete(*, common: CommonParameters | None = None) -> None:
    """Recursively delete sample data directory."""

    common = common or CommonParameters()

    _delete_sampledata(common.db_url)


if __name__ == "__main__":
    app()
