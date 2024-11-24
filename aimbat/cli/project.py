"""
Manage AIMBAT projects.

This command manages projects. By default, the project consists
of a file called `aimbat.db` in the current working directory. All aimbat
commands must be executed from the same directory.

The location (and name) of the project file may also be specified by
setting the AIMBAT_PROJECT environment variable to the desired filename.

Alternatively aimbat can be executed with a database url directly.
"""

from aimbat.lib.common import debug_callback
import typer


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


app = typer.Typer(
    name="project",
    no_args_is_help=True,
    callback=debug_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)


@app.command("create")
def project_cli_create(ctx: typer.Context) -> None:
    """Create new AIMBAT project."""
    _create_project(ctx.obj["DB_URL"])


@app.command("delete")
def project_cli_delete(ctx: typer.Context) -> None:
    """Delete project (note: this does not delete seismogram data)."""
    _delete_project(ctx.obj["DB_URL"])


@app.command("info")
def project_cli_info(ctx: typer.Context) -> None:
    """Show information on an exisiting project."""
    _print_project_info(ctx.obj["DB_URL"])


if __name__ == "__main__":
    app()
