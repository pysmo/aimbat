from typing import List
import click


def run_checks(sacfiles: List[str]) -> None:

    raise NotImplementedError


@click.command('checkdata')
@click.argument('sacfiles', nargs=-1, type=click.Path(exists=True), required=True)
def cli(sacfiles: List[str]) -> None:
    """Checks if there are any problems with the input SAC files."""

    raise NotImplementedError


if __name__ == "__main__":
    cli()
