"""Module to manage defaults used in an AIMBAT project."""

from aimbat import __file__ as aimbat_dir
from aimbat.lib.common import cli_enable_debug
import os
import click


# Defaults shipped with AIMBAT
AIMBAT_DEFAULTS_FILE = os.path.join(os.path.dirname(aimbat_dir), "lib/defaults.yml")

TAimbatDefault = float | int | bool | str


def _defaults_print_table(name: list[str] | None) -> None:
    from aimbat.lib.defaults import defaults_print_table

    defaults_print_table(name)


def _defaults_set_value(name: str, value: float | int | bool | str) -> None:
    from aimbat.lib.defaults import defaults_set_value

    defaults_set_value(name, value)


def _defaults_reset_value(name: str) -> None:
    from aimbat.lib.defaults import defaults_reset_value

    defaults_reset_value(name)


@click.group("defaults")
@click.pass_context
def defaults_cli(ctx: click.Context) -> None:
    """
    Lists or change AIMBAT defaults.

    This command lists various settings that are used in Aimbat.
    Defaults shipped with AIMBAT may be overriden here too.
    """
    cli_enable_debug(ctx)


@defaults_cli.command("list")
@click.argument("name", nargs=-1)
def defaults_cli_list(name: list[str] | None = None) -> None:
    """Print a table with defaults used in AIMBAT.

    One or more default names may be provided to filter output.
    """
    _defaults_print_table(name)


@defaults_cli.command("set")
@click.argument("name")
@click.argument("value")
def defaults_cli_set(name: str, value: float | int | bool | str) -> None:
    """Set an AIMBAT default to a new value."""
    _defaults_set_value(name, value)


@defaults_cli.command("reset")
@click.argument("name")
def defaults_cli_reset(name: str) -> None:
    """Reset an AIMBAT default to the initial value."""
    _defaults_reset_value(name)


if __name__ == "__main__":
    defaults_cli(obj={})
