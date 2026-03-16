"""Download or delete AIMBAT sample data.

The sampledata subcommand manages an example dataset that can be used
for testing or learning how to use AIMBAT.

The sample data source url can be viewed or changed via `aimbat default
<list/set> sampledata_src`. Likewise the sample data destination folder
be viewed or changed via `aimbat default <list/set> sampledata_dir`.
"""

from typing import Annotated

from cyclopts import App, Parameter

from aimbat._cli.common import DebugParameter, simple_exception

__all__ = ["sampledata_cli_download", "sampledata_cli_delete"]

app = App(name="sampledata", help=__doc__, help_format="markdown")


@app.command(name="download")
@simple_exception
def sampledata_cli_download(
    *,
    force: Annotated[
        bool, Parameter(help="Delete the download directory and re-download")
    ] = False,
    _: DebugParameter = DebugParameter(),
) -> None:
    """Download AIMBAT sample data.

    Downloads an example dataset to the directory specified in the
    `sampledata_dir` AIMBAT default variable.
    """
    from aimbat.utils import download_sampledata

    download_sampledata(force)


@app.command(name="delete")
@simple_exception
def sampledata_cli_delete(*, _: DebugParameter = DebugParameter()) -> None:
    """Recursively delete sample data directory."""
    from aimbat.utils import delete_sampledata

    delete_sampledata()


if __name__ == "__main__":
    app()
