"""Module to manage defaults used in an AIMBAT project."""

from aimbat.lib.common import ic
from aimbat.lib.types import AimbatDefaultAttribute
from aimbat.lib.misc.rich_utils import make_table
from aimbat.lib.models import AimbatDefault
from sqlmodel import Session, select
from rich.console import Console


def _get_instance(session: Session) -> AimbatDefault:
    """Return the AimbatDefault instance."""

    ic()

    aimbat_default = session.exec(select(AimbatDefault)).one_or_none()
    if aimbat_default is None:
        aimbat_default = AimbatDefault()
        session.add(aimbat_default)
    return aimbat_default


def get_default(
    session: Session, name: AimbatDefaultAttribute
) -> str | float | int | bool:
    """Return the value of an AIMBAT default."""

    ic()
    ic(name)

    return getattr(_get_instance(session), name)


def set_default(
    session: Session, name: AimbatDefaultAttribute, value: str | float | int | bool
) -> None:
    """Set the value of an AIMBAT default."""

    ic()
    ic(name, value)

    aimbat_default = _get_instance(session)
    setattr(aimbat_default, name, value)
    session.add(aimbat_default)
    session.commit()


def reset_default(session: Session, name: AimbatDefaultAttribute) -> None:
    """Reset the value of an AIMBAT default."""

    ic()
    ic(name)

    aimbat_default = _get_instance(session)
    aimbat_default.reset(name)

    session.add(aimbat_default)
    session.commit()


def print_defaults_table(session: Session) -> None:
    """Print a pretty table with AIMBAT configuration options."""

    ic()

    aimbat_defaults = _get_instance(session)

    table = make_table(title="AIMBAT Defaults")

    table.add_column("Name", justify="left", style="cyan", no_wrap=True)
    table.add_column("Value", justify="center", style="magenta")
    table.add_column("Description", justify="left", style="green")

    for key in AimbatDefault.model_fields.keys():
        if key == "id":
            continue
        table.add_row(
            key,
            str(getattr(aimbat_defaults, key)),
            aimbat_defaults.description(AimbatDefaultAttribute[key]),
        )

    console = Console()
    console.print(table)
