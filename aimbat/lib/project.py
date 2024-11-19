from aimbat.lib.defaults import defaults_load_global_values
from aimbat.lib.db import engine, AIMBAT_PROJECT
from aimbat.lib.common import cli_enable_debug
from sqlmodel import SQLModel, text
from pathlib import Path
from typing import Any
from icecream import ic  # type: ignore
import click
import aimbat.lib.models  # noqa: F401

ic.disable()


def project_exists() -> bool:
    """Check if AIMBAT project exists."""

    ic()
    ic(AIMBAT_PROJECT)

    return Path(AIMBAT_PROJECT).exists()


def project_new() -> None:
    """Create a new AIMBAT project."""

    ic()
    ic(AIMBAT_PROJECT)

    # stop here if there is an existing aimbat.db file
    if project_exists():
        raise FileExistsError(
            f"Unable to create a new project: found existing {AIMBAT_PROJECT=}!"
        )

    # create tables and load defaults
    SQLModel.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))  # for SQLite only
    defaults_load_global_values()


def project_del() -> None:
    """Delete the AIMBAT project."""

    ic()
    ic(AIMBAT_PROJECT)

    try:
        Path(AIMBAT_PROJECT).unlink()

    except FileNotFoundError:
        raise FileNotFoundError(
            f"Unable to delete project: {AIMBAT_PROJECT=} not found."
        )
    finally:
        engine.dispose()


def project_info() -> Any:
    """Show AIMBAT project information."""

    ic()
    ic(AIMBAT_PROJECT)

    if not Path(AIMBAT_PROJECT).exists():
        raise FileNotFoundError(f"Unable to show info: {AIMBAT_PROJECT=} not found!")

    raise NotImplementedError


@click.group("project")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Manage an AIMBAT project file.

    This command manages an AIMBAT project. By default, the project consists
    of a file called `aimbat.db` in the current working directory. All AIMBAT
    commands must be executed from the same directory.

    The location (and name) of the project file may also be specified by
    setting the AIMBAT_PROJECT environment variable to the desired filename.
    """
    cli_enable_debug(ctx)


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
    cli(obj={})
