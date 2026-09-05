"""Download or delete AIMBAT sample data.

The sampledata subcommand manages an example dataset that can be used
for testing or learning how to use AIMBAT.

The sample data destination folder can be viewed with `aimbat utils
settings` and changed by setting `AIMBAT_SAMPLEDATA_DIR`.
"""

from typing import Annotated

from cyclopts import App, Parameter

from aimbat._cli.common import ConfirmParameters, confirm_or_abort, handle_issues

__all__ = ["sampledata_cli_delete", "sampledata_cli_download"]

app = App(name="sampledata", help=__doc__, help_format="markdown")


@app.command(name="download")
@handle_issues
def sampledata_cli_download(
    *,
    force: Annotated[
        bool, Parameter(help="Delete the download directory and re-download")
    ] = False,
    confirm: ConfirmParameters = ConfirmParameters(),
) -> None:
    """Download AIMBAT sample data.

    Downloads an example dataset to the directory specified in the
    `sampledata_dir` AIMBAT default variable.
    """
    from aimbat import settings
    from aimbat.utils import download_sampledata

    if force:
        confirm_or_abort(
            f"Delete and replace the existing contents of {settings.sampledata_dir}?",
            yes=confirm.yes,
        )
    download_sampledata(force)


@app.command(name="delete")
@handle_issues
def sampledata_cli_delete(*, confirm: ConfirmParameters = ConfirmParameters()) -> None:
    """Recursively delete sample data directory."""
    from aimbat import settings
    from aimbat.utils import delete_sampledata

    confirm_or_abort(f"Recursively delete {settings.sampledata_dir}?", yes=confirm.yes)
    delete_sampledata()


if __name__ == "__main__":
    app()
