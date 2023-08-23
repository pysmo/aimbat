#!/usr/bin/env python

import click
from aimbat.lib.defaults import AimbatDefaults


@click.command('defaults')
@click.option('-g', '--global', 'global_only', is_flag=True,
              help="Ignore the local aimbat.yml configuration file and only show global defaults.")
@click.option('-y', '--yaml', 'print_yaml', is_flag=True,
              help="Output yaml instead of a table (to help with the creation of a local configuration file).")
def cli(global_only: bool, print_yaml: bool) -> None:
    """
    Lists default values for options that controll Aimbat behaviour.

    This command lists various settings that are used in Aimbat. They
    can be overridden by setting them to other values in an optional
    file called ``aimbat.yml``. Aimbat looks for this file in the
    current working directory.
    """
    defaults = AimbatDefaults(global_only=global_only)
    if print_yaml is True:
        defaults.print_yaml()
    else:
        defaults.print_table()


if __name__ == "__main__":
    cli()
