"""
Manage AIMBAT projects.

This command manages projects. By default, the project consists
of a file called `aimbat.db` in the current working directory. All aimbat
commands must be executed from the same directory. The location (and name) of
the project file may also be specified by setting the `AIMBAT_PROJECT`
environment variable to the desired filename. Alternatively, `aimbat` can be
executed with a database url directly.
"""

from aimbat.cli.common import GlobalParameters
from cyclopts import App


def _create_project(db_url: str | None) -> None:
    from aimbat.lib.project import create_project
    from aimbat.lib.common import engine_from_url

    create_project(engine_from_url(db_url))


def _delete_project(db_url: str | None) -> None:
    from aimbat.lib.project import delete_project
    from aimbat.lib.common import engine_from_url

    delete_project(engine_from_url(db_url))


def _print_project_info(db_url: str | None) -> None:
    from aimbat.lib.project import print_project_info
    from aimbat.lib.common import engine_from_url

    print_project_info(engine_from_url(db_url))


app = App(name="project", help=__doc__, help_format="markdown")


@app.command(name="create")
def cli_project_create(*, global_parameters: GlobalParameters | None = None) -> None:
    """Create new AIMBAT project."""

    global_parameters = global_parameters or GlobalParameters()

    _create_project(global_parameters.db_url)


@app.command(name="delete")
def cli_project_delete(*, global_parameters: GlobalParameters | None = None) -> None:
    """Delete project (note: this does *not* delete seismogram files)."""

    global_parameters = global_parameters or GlobalParameters()

    _delete_project(global_parameters.db_url)


@app.command(name="info")
def cli_project_info(*, global_parameters: GlobalParameters | None = None) -> None:
    """Show information on an exisiting project."""

    global_parameters = global_parameters or GlobalParameters()

    _print_project_info(global_parameters.db_url)


if __name__ == "__main__":
    app()
