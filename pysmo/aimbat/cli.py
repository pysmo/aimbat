#!/usr/bin/env python

from pysmo.aimbat import defaults
from importlib import metadata
import click

try:
    __version__ = metadata.version("pysmo.aimbat")
except Exception:
    __version__ = "unknown"


@click.group()
@click.version_option(version=__version__)
def cli():
    pass


cli.add_command(defaults.cli)


if __name__ == "__main__":
    cli()
