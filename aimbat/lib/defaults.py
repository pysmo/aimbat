"""Manage defaults used in an AIMBAT project."""

from aimbat.lib.common import logger
from aimbat.lib.misc.rich_utils import make_table
from aimbat.lib.models import AimbatDefaults
from aimbat.lib.typing import (
    ProjectDefault,
    ProjectDefaultBool,
    ProjectDefaultStr,
    ProjectDefaultTimedelta,
)
from sqlmodel import Session, select
from typing import overload
from datetime import timedelta
from rich.console import Console


def _get_instance(session: Session) -> AimbatDefaults:
    """Return the AimbatDefault instance.

    Parameters:
        session: Database session.

    Returns:
        AimbatDefaults instance.
    """

    logger.info("Retrieving AimbatDefaults instance.")

    aimbat_default = session.exec(select(AimbatDefaults)).one_or_none()
    if aimbat_default is None:
        aimbat_default = AimbatDefaults()
        session.add(aimbat_default)
    return aimbat_default


@overload
def get_default(session: Session, name: ProjectDefaultTimedelta) -> timedelta: ...


@overload
def get_default(session: Session, name: ProjectDefaultBool) -> bool: ...


@overload
def get_default(session: Session, name: ProjectDefaultStr) -> str: ...


@overload
def get_default(session: Session, name: ProjectDefault) -> timedelta | bool | str: ...


def get_default(session: Session, name: ProjectDefault) -> timedelta | bool | str:
    """Return the value of an AIMBAT default.

    Parameters:
        session: Database session.
        name: Name of the default.

    Returns:
        Value of the default.
    """

    logger.info(f"Getting value of {name} default.")

    return getattr(_get_instance(session), name)


@overload
def set_default(
    session: Session, name: ProjectDefaultTimedelta, value: timedelta
) -> None: ...


@overload
def set_default(session: Session, name: ProjectDefaultBool, value: bool) -> None: ...


@overload
def set_default(session: Session, name: ProjectDefaultStr, value: str) -> None: ...


@overload
def set_default(
    session: Session, name: ProjectDefault, value: timedelta | bool | str
) -> None: ...


def set_default(
    session: Session, name: ProjectDefault, value: timedelta | bool | str
) -> None:
    """Set the value of an AIMBAT default.

    Parameters:
        session: Database session.
        name: Name of the default.
        value: Value to set the default to.
    """

    logger.info(f"Setting {name} default to {value}.")

    aimbat_default = _get_instance(session)
    value = getattr(
        AimbatDefaults.model_validate(aimbat_default, update={name: value}), name
    )
    setattr(aimbat_default, name, value)
    session.add(aimbat_default)
    session.commit()


def reset_default(session: Session, name: ProjectDefault) -> None:
    """Reset the value of an AIMBAT default.

    Parameters:
        session: Database session.
        name: Name of the default.
    """

    logger.info(f"Resetting {name} default.")

    aimbat_default = _get_instance(session)
    aimbat_default.reset(name)

    session.add(aimbat_default)
    session.commit()


def print_defaults_table(session: Session) -> None:
    """Print a pretty table with AIMBAT configuration options.

    Parameters:
        session: Database session.
    """

    logger.info("Printing AIMBAT defaults table.")

    aimbat_defaults = _get_instance(session)

    table = make_table(title="AIMBAT Defaults")

    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Value", justify="center", style="magenta")
    table.add_column("Description", justify="left", style="green")

    for key in AimbatDefaults.model_fields.keys():
        value = getattr(aimbat_defaults, key)
        if isinstance(value, timedelta):
            value = f"{value.total_seconds()}s"
        if key == "id":
            continue
        table.add_row(
            key,
            str(value),
            aimbat_defaults.description(ProjectDefault[key.upper()]),
        )

    console = Console()
    console.print(table)
