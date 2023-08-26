import aimbat.lib.project as project
from ..lib.defaults import (
    defaults_print_table,
    defaults_reset_value,
    defaults_set_value
)
from typing import List
import click


def get_engine():  # type: ignore
    engine = project.project_db_engine()
    return engine


@click.group("defaults")
def cli() -> None:
    """
    Lists or change AIMBAT defaults.

    This command lists various settings that are used in Aimbat.
    Defaults shipped with AIMBAT may be overriden here too.
    """


@cli.command("list")
@click.argument("name", nargs=-1)
def list_defaults(name: List[str] | None = None) -> None:
    """Print a table with defaults used in AIMBAT.

    One or more default names may be provided to filter output.
    """

    engine = get_engine()
    defaults_print_table(engine, name)


@cli.command("set")
@click.argument("name")
@click.argument("value")
def set_default(name: str, value: float | int | bool | str) -> None:
    """Set an AIMBAT default to a new value."""

    engine = get_engine()
    defaults_set_value(engine, name, value)


@cli.command("reset")
@click.argument("name")
def reset_default(name: str) -> None:
    """Reset an AIMBAT default to the initial value."""

    engine = get_engine()
    defaults_reset_value(engine, name)


if __name__ == "__main__":
    cli()
