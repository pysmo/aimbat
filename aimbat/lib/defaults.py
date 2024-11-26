"""Module to manage defaults used in an AIMBAT project."""

from aimbat import __file__ as aimbat_dir
from aimbat.lib.common import ic, string_to_type
from sqlmodel import Session, select
from rich.console import Console
from rich.table import Table
from aimbat.lib.models import AimbatDefault
import os
import yaml


# Defaults shipped with AIMBAT
AIMBAT_DEFAULTS_FILE = os.path.join(os.path.dirname(aimbat_dir), "lib/defaults.yml")


def load_global_defaults(session: Session) -> None:
    """Read defaults shipped with AIMBAT from yaml file."""
    ic()
    ic(session)

    with open(AIMBAT_DEFAULTS_FILE, "r") as stream:
        data: list[dict[str, str | str | float | int | bool]] = yaml.safe_load(stream)

        for item in data:
            session.add(AimbatDefault(**item))
        session.commit()


def _select_single_item(session: Session, name: str) -> AimbatDefault:
    """Return a single AimbatDefault item."""
    ic()
    ic(name, session)

    statement = select(AimbatDefault).where(AimbatDefault.name == name)
    result = session.exec(statement).one_or_none()

    if result is None:
        raise RuntimeError(f"No default with {name=}.")
    return result


def get_default(session: Session, name: str) -> str | float | int | bool:
    """Return the value of an AIMBAT default."""
    ic()
    ic(name)
    return _select_single_item(session, name).value


def set_default(session: Session, name: str, value: str | float | int | bool) -> None:
    """Set the value of an AIMBAT default."""
    ic()
    ic(name, value)

    # Get the AimbatDefault instance
    aimbat_default = _select_single_item(session, name)

    is_of_type = aimbat_default.is_of_type

    if isinstance(value, str) and is_of_type != "str":
        value = string_to_type(is_of_type, value)

    aimbat_default.value = value
    session.add(aimbat_default)
    session.commit()


def reset_default(session: Session, name: str) -> None:
    """Reset the value of an AIMBAT default."""
    ic()
    ic(name)

    aimbat_default = _select_single_item(session, name)
    aimbat_default.reset_value()

    session.add(aimbat_default)
    session.commit()


def print_defaults_table(
    session: Session, select_names: list[str] | None = None
) -> None:
    """Print a pretty table with AIMBAT configuration options."""
    ic()
    ic(select_names)

    if not select_names:
        select_names = []

    defaults = session.exec(select(AimbatDefault)).all()

    table = Table(title="AIMBAT Defaults")

    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Value", justify="center", style="magenta")
    table.add_column("Description", justify="left", style="green")

    for aimbat_default in defaults:
        # names with "_test_" in them are in the table,
        # but should only be used in unit tests
        if (
            "_test_" not in aimbat_default.name
            and not select_names
            or aimbat_default.name in select_names
        ):
            table.add_row(
                aimbat_default.name,
                str(aimbat_default.value),
                aimbat_default.description,
            )

    console = Console()
    console.print(table)
