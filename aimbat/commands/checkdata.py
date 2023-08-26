from typing import List
import click
# from pysmo import SAC


@click.command('checkdata')
@click.argument('sacfiles', nargs=-1, type=click.Path(exists=True), required=True)
@click.option('-t', '--tolerance', type=int, default=None, show_default=True,
              help=('Optionally resample seismograms with this new sampling interval.'))
def cli(sacfiles: List[str], tolerance: int) -> None:
    """
    Checks if there are any problems with the input SAC files.
    """
    run_checks(sacfiles)


def run_checks(sacfiles: List[str]) -> None:
    for sacfile in sacfiles:
        print(f"checking {sacfile}")


if __name__ == "__main__":
    cli()
