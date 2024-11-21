from aimbat.lib.db import AIMBAT_PROJECT
from aimbat.lib.common import cli_enable_debug
import click


def _project_new() -> None:
    from aimbat.lib.project import project_new

    project_new()


def _project_del() -> None:
    from aimbat.lib.project import project_del

    project_del()


def _project_print_info() -> None:
    from aimbat.lib.project import project_print_info

    project_print_info()


@click.group("project")
@click.pass_context
def project_cli(ctx: click.Context) -> None:
    """Manage an AIMBAT project file.

    This command manages an AIMBAT project. By default, the project consists
    of a file called `aimbat.db` in the current working directory. All AIMBAT
    commands must be executed from the same directory.

    The location (and name) of the project file may also be specified by
    setting the AIMBAT_PROJECT environment variable to the desired filename.
    """
    cli_enable_debug(ctx)


@project_cli.command("new")
def project_cli_new() -> None:
    """Create new AIMBAT project."""
    try:
        _project_new()
        print(f"Created new AIMBAT project in {AIMBAT_PROJECT}.")
    except FileExistsError as e:
        print(e)


@project_cli.command("del")
@click.confirmation_option(prompt="Are you sure?")
def project_cli_del() -> None:
    """Delete project (note: this does not delete seismogram data)."""
    try:
        _project_del()
    except FileNotFoundError as e:
        print(e)


@project_cli.command("info")
def project_cli_info() -> None:
    """Show information on an exisiting project."""
    try:
        _project_print_info()
    except FileNotFoundError as e:
        print(e)


if __name__ == "__main__":
    project_cli(obj={})
