"""Manage defaults used in an AIMBAT project.

This command lists various settings that are used in Aimbat.
Defaults shipped with AIMBAT may be overriden here too.
"""

from aimbat import __file__ as aimbat_dir
from aimbat.lib.common import debug_callback
from typing import Annotated, Optional
import os
import typer


# Defaults shipped with AIMBAT
AIMBAT_DEFAULTS_FILE = os.path.join(os.path.dirname(aimbat_dir), "lib/defaults.yml")

TAimbatDefault = float | int | bool | str


def _print_defaults_table(name: list[str] | None, db_url: str | None) -> None:
    from aimbat.lib.defaults import print_defaults_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_defaults_table(session, name)


def _set_default(
    name: str, value: float | int | bool | str, db_url: str | None
) -> None:
    from aimbat.lib.defaults import set_default
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        set_default(session, name, value)


def _reset_default(name: str, db_url: str | None) -> None:
    from aimbat.lib.defaults import reset_default
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        reset_default(session, name)


app = typer.Typer(
    name="defaults",
    no_args_is_help=True,
    callback=debug_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)


@app.command("list")
def defaults_cli_list(
    ctx: typer.Context,
    name: Annotated[
        Optional[list[str]],
        typer.Argument(
            help="Name(s) of AIMBAT defaults to include in the table (space separated)."
        ),
    ] = None,
) -> None:
    """Print a table with defaults used in AIMBAT.

    By default all defaults are included. One or more default names may be provided to filter output.
    """
    db_url = ctx.obj["DB_URL"]
    _print_defaults_table(name, db_url)


@app.command("set")
def defaults_cli_set(ctx: typer.Context, name: str, value: str) -> None:
    """Set an AIMBAT default to a new value."""
    db_url = ctx.obj["DB_URL"]
    _set_default(name, value, db_url)


@app.command("reset")
def defaults_cli_reset(ctx: typer.Context, name: str) -> None:
    """Reset an AIMBAT default to the initial value."""
    db_url = ctx.obj["DB_URL"]
    _reset_default(name, db_url)


if __name__ == "__main__":
    app()
