#!/usr/bin/env python

import click


@click.group('project')
def cli() -> None:
    """Manage an AIMBAT project in this directory.

    This command manages an AIMBAT project stored in `aimbat.db`. All AIMBAT
    commands must be executed in the directory where this file is stored.
    """
    pass


@cli.command('new')
def new_project() -> None:
    """Create a new project in the current directory."""
    raise NotImplementedError


@cli.command('del')
def del_project() -> None:
    """Delete existing project (note: this does not delete seismogram data)."""
    raise NotImplementedError


@cli.command('info')
def info_project() -> None:
    """Show information on an exisiting project."""
    raise NotImplementedError


if __name__ == "__main__":
    cli()
