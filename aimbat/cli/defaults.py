"""Manage defaults used in an AIMBAT project.

This command lists various settings that are used in AIMBAT.
Defaults shipped with AIMBAT may be overriden here too.
"""

from aimbat.cli.common import CommonParameters, convert_to_type
from aimbat.lib.typing import ProjectDefault
from datetime import timedelta
from cyclopts import App


def _set_default(
    default_name: ProjectDefault,
    default_value: float | int | bool | str | timedelta,
    db_url: str | None,
) -> None:
    from aimbat.lib.defaults import set_default
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    converted_value = convert_to_type(default_name, default_value)

    with Session(engine_from_url(db_url)) as session:
        set_default(session, default_name, converted_value)


def _get_default(name: ProjectDefault, db_url: str) -> None:
    from aimbat.lib.defaults import get_default
    from aimbat.lib.common import engine_from_url
    from sqlmodel import Session

    with Session(engine_from_url(db_url)) as session:
        value = get_default(session, name)
        if isinstance(value, timedelta):
            print(value.total_seconds())
        print(value)


def _reset_default(name: ProjectDefault, db_url: str | None) -> None:
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


app = App(name="defaults", help=__doc__, help_format="markdown")


@app.command(name="get")
def cli_defaults_get(
    name: ProjectDefault, *, common: CommonParameters | None = None
) -> None:
    """Get an AIMBAT default value.

    Parameters:
        name: Name of the default variable.
    """

    common = common or CommonParameters()

    _get_default(name, common.db_url)


@app.command(name="set")
def cli_defaults_set(
    name: ProjectDefault, value: str, *, common: CommonParameters | None = None
) -> None:
    """Set an AIMBAT default to a new value.

    Parameters:
        name: Name of the default variable.
        value: Value of the default variable.
    """

    common = common or CommonParameters()

    _set_default(name, value, common.db_url)


@app.command(name="reset")
def cli_defaults_reset(
    name: ProjectDefault, *, common: CommonParameters | None = None
) -> None:
    """Reset an AIMBAT default to the initial value.

    Parameters:
        name: Name of the default variable.
    """

    common = common or CommonParameters()

    _reset_default(name, common.db_url)


@app.command(name="list")
def cli_defaults_list(*, common: CommonParameters | None = None) -> None:
    """Print a table with defaults used in AIMBAT."""

    common = common or CommonParameters()

    _print_defaults_table(common.db_url)


if __name__ == "__main__":
    app()
