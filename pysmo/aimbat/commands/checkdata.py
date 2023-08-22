#!/usr/bin/env python

import click
from pysmo import SacIO


@click.command('checkdata')
@click.argument('sacfiles', nargs=-1, type=click.Path(exists=True), required=True)
@click.option('-t', '--tolerance', type=int, default=None, show_default=True,
              help=('Optionally resample seismograms with this new sampling interval.'))
def cli(sacfiles, tolerance: int):
    """
    Checks if there are any problems with the input SAC files.
    """
    run_checks(sacfiles)


def run_checks(sacfiles):
    pass


if __name__ == "__main__":
    cli()
