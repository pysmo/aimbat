"""
Manage AIMBAT projects.

This command manages projects. By default, the project consists
of a file called `aimbat.db` in the current working directory. All aimbat
commands must be executed from the same directory. The location (and name) of
the project file may also be specified by setting the `AIMBAT_PROJECT`
environment variable to the desired filename. Alternatively, `aimbat` can be
executed with a database url directly.
"""

from ._common import GlobalParameters, simple_exception
from cyclopts import App

app = App(name="project", help=__doc__, help_format="markdown")


@app.command(name="create")
@simple_exception
def cli_project_create(*, global_parameters: GlobalParameters | None = None) -> None:
    """Create new AIMBAT project."""
    from aimbat.db import engine
    from aimbat.core import create_project

    global_parameters = global_parameters or GlobalParameters()

    create_project(engine)


@app.command(name="delete")
@simple_exception
def cli_project_delete(*, global_parameters: GlobalParameters | None = None) -> None:
    """Delete project (note: this does *not* delete seismogram files)."""
    from aimbat.db import engine
    from aimbat.core import delete_project

    global_parameters = global_parameters or GlobalParameters()

    delete_project(engine)


@app.command(name="info")
@simple_exception
def cli_project_info(*, global_parameters: GlobalParameters | None = None) -> None:
    """Show information on an exisiting project."""

    from aimbat.db import engine
    from aimbat.core import print_project_info

    global_parameters = global_parameters or GlobalParameters()

    print_project_info(engine)


if __name__ == "__main__":
    app()
