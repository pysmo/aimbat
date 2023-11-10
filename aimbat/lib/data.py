from pathlib import Path
from aimbat.lib import models  # noqa: F401
import click


def add_data(sacfiles: list[Path]) -> None:
    for sacfile in sacfiles:
        print(sacfile)


@click.group("data")
def cli() -> None:
    """Manage data (Seismogram files) in an AIMBAT project."""
    pass


@cli.command("add")
@click.argument("sacfiles", nargs=-1, type=click.Path(exists=True), required=True)
def cli_data_add(sacfiles: list[Path]) -> None:
    """Add data to an AIMBAT project."""
    add_data(sacfiles)


if __name__ == "__main__":
    cli()
