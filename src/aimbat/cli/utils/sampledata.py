"""Download or delete AIMBAT sample data.

The sampledata subcommand manages an example dataset that can be used
for testing or learning how to use AIMBAT.

The sample data source url can be viewed or changed via `aimbat default
<list/set> sampledata_src`. Likewise the sample data destination folder
be viewed or changed via `aimbat default <list/set> sampledata_dir`.
"""

from aimbat.cli.common import GlobalParameters, simple_exception
from cyclopts import App


@simple_exception
def _delete_sampledata() -> None:
    from aimbat.lib.utils.sampledata import delete_sampledata

    delete_sampledata()


@simple_exception
def _download_sampledata(force: bool = False) -> None:
    from aimbat.lib.utils.sampledata import download_sampledata

    download_sampledata(force)


app = App(name="sampledata", help=__doc__, help_format="markdown")


@app.command(name="download")
def sampledata_cli_download(
    *, force: bool = False, global_parameters: GlobalParameters | None = None
) -> None:
    """Download AIMBAT sample data.

    Downloads an example dataset to the directory specified in the
    `sampledata_dir` AIMBAT default variable.

    Args:
        force: Delete the download directory and re-download."
    """

    global_parameters = global_parameters or GlobalParameters()

    _download_sampledata(force)


@app.command(name="delete")
def sampledata_cli_delete(*, global_parameters: GlobalParameters | None = None) -> None:
    """Recursively delete sample data directory."""

    global_parameters = global_parameters or GlobalParameters()

    _delete_sampledata()


if __name__ == "__main__":
    app()
