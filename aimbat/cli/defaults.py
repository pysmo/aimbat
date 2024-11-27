"""Manage defaults used in an AIMBAT project.

This command lists various settings that are used in Aimbat.
Defaults shipped with AIMBAT may be overriden here too.
"""

from aimbat.lib.common import debug_callback, string_to_type
from aimbat.lib.types import AimbatDefaultAttribute
import typer


def _set_default(
    name: AimbatDefaultAttribute, value: float | int | bool | str, db_url: str | None
) -> None:
    from aimbat.lib.defaults import set_default
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    if isinstance(value, str):
        value = string_to_type(value)
        print(value)

    with Session(engine_from_url(db_url)) as session:
        set_default(session, name, value)


def _get_default(name: AimbatDefaultAttribute, db_url: str) -> None:
    from aimbat.lib.defaults import get_default
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print(get_default(session, name))


def _reset_default(name: AimbatDefaultAttribute, db_url: str | None) -> None:
    from aimbat.lib.defaults import reset_default
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        reset_default(session, name)


def _print_defaults_table(db_url: str) -> None:
    from aimbat.lib.defaults import print_defaults_table
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        print_defaults_table(session)


app = typer.Typer(
    name="defaults",
    no_args_is_help=True,
    callback=debug_callback,
    short_help=__doc__.partition("\n")[0],
    help=__doc__,
)


@app.command("get")
def defaults_cli_get(ctx: typer.Context, name: AimbatDefaultAttribute) -> None:
    """Get an AIMBAT default value."""
    db_url = ctx.obj["DB_URL"]
    _get_default(name, db_url)


@app.command("set")
def defaults_cli_set(
    ctx: typer.Context, name: AimbatDefaultAttribute, value: str
) -> None:
    """Set an AIMBAT default to a new value."""
    db_url = ctx.obj["DB_URL"]
    _set_default(name, value, db_url)


@app.command("reset")
def defaults_cli_reset(ctx: typer.Context, name: AimbatDefaultAttribute) -> None:
    """Reset an AIMBAT default to the initial value."""
    db_url = ctx.obj["DB_URL"]
    _reset_default(name, db_url)


@app.command("list")
def defaults_cli_list(
    ctx: typer.Context,
) -> None:
    """Print a table with defaults used in AIMBAT."""
    db_url = ctx.obj["DB_URL"]
    _print_defaults_table(db_url)


if __name__ == "__main__":
    app()
