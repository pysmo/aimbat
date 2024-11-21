from aimbat.lib.common import cli_enable_debug
import click


def _sampledata_delete() -> None:
    from aimbat.lib.sampledata import sampledata_delete

    sampledata_delete()


def _sampledata_download(force: bool = False) -> None:
    from aimbat.lib.sampledata import sampledata_download

    sampledata_download(force)


@click.group("sampledata")
@click.pass_context
def sampledata_cli(ctx: click.Context) -> None:
    """Download aimbat sample data and save it to a folder.

    The sample data source url can be viewed or changed via `aimbat default
    <list/set> sampledata_src`. Likewise the sample data destination folder
    be viewed or changed via `aimbat default <list/set> sampledata_dir`."""
    cli_enable_debug(ctx)


@sampledata_cli.command("delete")
def sampledata_cli_delete() -> None:
    """Recursively delete sample data directory."""

    _sampledata_delete()


@sampledata_cli.command("download")
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Remove target directory if it already exists and re-download sample data.",
)
def sampledata_cli_download(force: bool) -> None:
    """Download aimbat sample data."""

    _sampledata_download(force)


if __name__ == "__main__":
    sampledata_cli(obj={})
