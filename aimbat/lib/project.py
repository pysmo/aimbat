from aimbat.lib.defaults import defaults_load_global_values
from aimbat.lib.db import engine, AIMBAT_PROJECT
from sqlmodel import SQLModel
from pathlib import Path
from typing import Any
import click
import aimbat.lib.models  # noqa: F401


def project_exists() -> bool:
    """Check if AIMBAT project exists."""
    return Path(AIMBAT_PROJECT).exists()


def project_new() -> None:
    """Create a new AIMBAT project."""

    # stop here if there is an existing aimbat.db file
    if project_exists():
        raise FileExistsError(
            f"Unable to create a new project: found existing {AIMBAT_PROJECT=}!"
        )

    # create tables and load defaults
    SQLModel.metadata.create_all(engine)
    defaults_load_global_values()


def project_del() -> None:
    """Delete the AIMBAT project."""

    try:
        Path(AIMBAT_PROJECT).unlink()

    except FileNotFoundError:
        raise FileNotFoundError(
            f"Unable to delete project: {AIMBAT_PROJECT=} not found."
        )


def project_info() -> Any:
    """Show AIMBAT project information."""

    if not Path(AIMBAT_PROJECT).exists():
        raise FileNotFoundError(f"Unable to show info: {AIMBAT_PROJECT=} not found!")

    raise NotImplementedError


@click.group("project")
def cli() -> None:
    """Manage an AIMBAT project file.

    This command manages an AIMBAT project. By default, the project consists
    of a file called `aimbat.db` in the current working directory. All AIMBAT
    commands must be executed from the same directory.

    The location (and name) of the project file may also be specified by
    setting the AIMBAT_PROJECT environment variable to the desired filename.
    """
    pass


@cli.command("new")
def cli_project_new() -> None:
    """Creates a new AIMBAT project ."""
    try:
        project_new()
        print(f"Created new AIMBAT project in {AIMBAT_PROJECT}.")
    except FileExistsError as e:
        print(e)


@cli.command("del")
@click.confirmation_option(prompt="Are you sure?")
def cli_project_del() -> None:
    """Delete project (note: this does not delete seismogram data)."""
    try:
        project_del()
    except FileNotFoundError as e:
        print(e)


@cli.command("info")
def cli_project_info() -> None:
    """Show information on an exisiting project."""
    try:
        project_info()
    except FileNotFoundError as e:
        print(e)


if __name__ == "__main__":
    cli()
