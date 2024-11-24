"""Module to manage defaults used in an AIMBAT project."""

from aimbat import __file__ as aimbat_dir
from aimbat.lib.common import ic
from aimbat.lib.types import TAimbatDefault
from sqlmodel import SQLModel, Field, Session, select
from rich.console import Console
from rich.table import Table
import os
import yaml


# Defaults shipped with AIMBAT
AIMBAT_DEFAULTS_FILE = os.path.join(os.path.dirname(aimbat_dir), "lib/defaults.yml")


def _format_value(is_of_type: str, value: str) -> TAimbatDefault:
    ic()
    ic(is_of_type, value)
    if is_of_type == "float":
        return float(value)
    elif is_of_type == "int":
        return int(value)
    # different ways of setting boolean defaults
    elif is_of_type == "bool" and str(value).lower() in ["true", "1", "yes"]:
        return True
    elif is_of_type == "bool" and str(value).lower() in ["false", "0", "no"]:
        return False
    elif is_of_type == "bool":
        raise ValueError(f"Unable to set to use {value=}. Must be of type {is_of_type}")
    # Only strings should be left at this point anyway...
    elif is_of_type == "str":
        return str(value)
    else:
        raise RuntimeError(f"Unable to set default with {value=}.")  # pragma: no cover


class AimbatDefault(SQLModel, table=True):
    """Class to store AIMBAT defaults."""

    id: int | None = Field(primary_key=True)
    name: str = Field(unique=True)
    is_of_type: str = Field(allow_mutation=False)
    description: str = Field(allow_mutation=False)
    initial_value: str = Field(allow_mutation=False)
    fvalue: float | None = None
    ivalue: int | None = None
    bvalue: bool | None = None
    svalue: str | None = None

    def __init__(self, **kwargs: str | TAimbatDefault) -> None:
        ic()
        ic(kwargs)
        super().__init__(**kwargs)
        self.reset_value()

    def reset_value(self) -> None:
        self.value = _format_value(self.is_of_type, self.initial_value)

    @property
    def value(self) -> TAimbatDefault:
        """Return default value"""
        if self.is_of_type == "float" and self.fvalue is not None:
            return self.fvalue
        elif self.is_of_type == "int" and self.ivalue is not None:
            return self.ivalue
        elif self.is_of_type == "bool" and self.bvalue is not None:
            return self.bvalue
        elif self.is_of_type == "str" and self.svalue is not None:
            return self.svalue
        raise RuntimeError("Unable to return value")  # pragma: no cover

    @value.setter
    def value(self, value: TAimbatDefault) -> None:
        """Set a default value"""
        ic()
        ic(value)
        if self.is_of_type == "float" and isinstance(value, float):
            self.fvalue = value
        elif self.is_of_type == "int" and isinstance(value, int):
            self.ivalue = value
        elif self.is_of_type == "bool" and isinstance(value, bool):
            self.bvalue = value
        elif self.is_of_type == "str" and isinstance(value, str):
            self.svalue = value
        else:
            raise RuntimeError(
                "Unable to assign {self.name} with value: {self.initial_value}."
            )  # pragma: no cover


def load_global_defaults(session: Session) -> None:
    """Read defaults shipped with AIMBAT from yaml file."""
    ic()
    ic(session)

    with open(AIMBAT_DEFAULTS_FILE, "r") as stream:
        data: list[dict[str, str | TAimbatDefault]] = yaml.safe_load(stream)

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


def get_default(session: Session, name: str) -> TAimbatDefault:
    """Return the value of an AIMBAT default."""
    ic()
    ic(name)
    return _select_single_item(session, name).value


def set_default(session: Session, name: str, value: TAimbatDefault) -> None:
    """Set the value of an AIMBAT default."""
    ic()
    ic(name, value)

    # Get the AimbatDefault instance
    aimbat_default = _select_single_item(session, name)

    is_of_type = aimbat_default.is_of_type

    if isinstance(value, str) and is_of_type != "str":
        value = _format_value(is_of_type, value)

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
