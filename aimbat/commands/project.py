#!/usr/bin/env python

from ..lib.project import project_new, project_del, project_info
import click


@click.group('project')
def cli() -> None:
    """Manage an AIMBAT project file.

    This command manages an AIMBAT project. By default, the project consists
    of a file called `aimbat.db` in the current working directory. All AIMBAT
    commands must be executed from the same directory.

    The location (and name) of the project file may also be specified by
    setting the AIMBAT_PROJECT environment variable to the desired filename.
    """
    pass


@cli.command('new')
def cli_project_new() -> None:
    """Creates a new AIMBAT project ."""
    project_new()


@cli.command('del')
@click.confirmation_option(prompt="Are you sure?")
def cli_project_del() -> None:
    """Delete project (note: this does not delete seismogram data)."""
    project_del()


@cli.command('info')
def cli_project_info() -> None:
    """Show information on an exisiting project."""
    project_info()


if __name__ == "__main__":
    cli()
