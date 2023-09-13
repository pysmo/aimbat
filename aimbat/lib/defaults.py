from aimbat.lib.db import engine
from aimbat import __file__ as aimbat_dir
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound
from typing import List
from prettytable import PrettyTable
from .models import AimbatDefault
import os
import yaml
import click


# Defaults shipped with AIMBAT
AIMBAT_DEFAULTS_FILE = os.path.join(os.path.dirname(aimbat_dir), "lib/defaults.yml")


class AimbatDefaultNotFound(Exception):
    pass


class AimbatDefaultTypeError(Exception):
    pass


def defaults_load_global_values() -> None:
    """Read defaults shipped with AIMBAT from yaml file."""

    with open(AIMBAT_DEFAULTS_FILE, "r") as stream:
        data = yaml.safe_load(stream)

    with Session(engine) as session:
        for item in data:
            session.add(AimbatDefault(**item))
        session.commit()


def _get_single_item(name: str) -> AimbatDefault:
    """Return a single AimbatDefault item."""

    with Session(engine) as session:
        statement = select(AimbatDefault).where(AimbatDefault.name == name)
        results = session.exec(statement)

        try:
            return results.one()
        except NoResultFound:
            raise AimbatDefaultNotFound(f"No default with {name=}.")


def typed_value(default: AimbatDefault) -> float | int | bool | str | None:
    """Return the typed value from AimbatDefault.name."""

    # the type we need to return
    is_of_type = default.is_of_type

    # return the type from the correct column
    if is_of_type == "float":
        return default.fvalue
    elif is_of_type == "int":
        return default.ivalue
    elif is_of_type == "bool":
        return default.bvalue
    return default.svalue


def defaults_get_value(name: str) -> float | int | bool | str | None:
    """Return the value of an AIMBAT default."""

    default = _get_single_item(name)
    return typed_value(default)


def defaults_set_value(name: str, value: float | int | str | bool) -> None:
    """Set the value of an AIMBAT default."""

    # Get the AimbatDefault instance
    default = _get_single_item(name)

    # new value must be of this type
    is_of_type = default.is_of_type

    # set fvalue to float(value) or raise exception
    if is_of_type == "float":
        try:
            default.fvalue = float(value)
        except ValueError:
            raise AimbatDefaultTypeError(
                f"Unable to set default {name} to {value}. "
                + f"must be of type {is_of_type}"
            )

    # set ivalue to int(value) or raise exception
    elif is_of_type == "int":
        try:
            default.ivalue = int(value)
        except ValueError:
            raise AimbatDefaultTypeError(
                f"Unable to set default {name} to {value}. "
                + f"Must be of type {is_of_type}"
            )

    # different ways of setting boolean defaults
    elif is_of_type == "bool" and str(value).lower() in ["true", "1", "yes"]:
        default.bvalue = True
    elif is_of_type == "bool" and str(value).lower() in ["false", "0", "no"]:
        default.bvalue = False
    elif is_of_type == "bool":
        raise AimbatDefaultTypeError(
            f"Unable to set default {name} to {value}. "
            + f"Must be of type {is_of_type}"
        )

    # Only strings should be left at this point anyway...
    elif is_of_type == "str":
        default.svalue = str(value)

    # ... so there really shouldn't be any way to get here.
    else:
        raise RuntimeError(
            f"Unable to set default {name} to {value}."
        )  # pragma: no cover

    # commit the changes
    with Session(engine) as session:
        session.add(default)
        session.commit()
        session.refresh(default)


def defaults_reset_value(name: str) -> None:
    """Reset the value of an AIMBAT default."""

    # get single item
    default = _get_single_item(name)

    # get type and initial value
    is_of_type, initial_value = default.is_of_type, default.initial_value

    # set correct attribute
    if is_of_type == "float":
        default.fvalue = float(initial_value)
    elif is_of_type == "int":
        default.ivalue = int(initial_value)
    elif is_of_type == "bool":
        default.bvalue = bool(initial_value)
    else:
        default.svalue = initial_value

    # commit changes
    with Session(engine) as session:
        session.add(default)
        session.commit()
        session.refresh(default)


def defaults_print_table(select_names: List[str] | None = None) -> None:
    """Print a pretty table with AIMBAT configuration options."""

    if not select_names:
        select_names = []

    # get all items
    with Session(engine) as session:
        statement = select(AimbatDefault)
        defaults = session.exec(statement).all()

    # print the table
    table = PrettyTable()
    table.field_names = ["Name", "Value", "Description"]
    for default in defaults:
        # names with "_test_" in them are in the table,
        # but should only be used in unit tests
        if (
            "_test_" not in default.name
            and not select_names
            or default.name in select_names
        ):
            table.add_row([default.name, typed_value(default), default.description])
    print(table)


@click.group("defaults")
def cli() -> None:
    """
    Lists or change AIMBAT defaults.

    This command lists various settings that are used in Aimbat.
    Defaults shipped with AIMBAT may be overriden here too.
    """


@cli.command("list")
@click.argument("name", nargs=-1)
def list_defaults(name: List[str] | None = None) -> None:
    """Print a table with defaults used in AIMBAT.

    One or more default names may be provided to filter output.
    """

    defaults_print_table(name)


@cli.command("set")
@click.argument("name")
@click.argument("value")
def set_default(name: str, value: float | int | bool | str) -> None:
    """Set an AIMBAT default to a new value."""

    defaults_set_value(name, value)


@cli.command("reset")
@click.argument("name")
def reset_default(name: str) -> None:
    """Reset an AIMBAT default to the initial value."""

    defaults_reset_value(name)


if __name__ == "__main__":
    cli()
