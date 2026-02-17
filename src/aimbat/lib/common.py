"""Common functions for AIMBAT."""

from aimbat.config import settings
from aimbat.lib.models import (
    AimbatTypes,
    AimbatDataSource,
    AimbatStation,
    AimbatEvent,
    AimbatEventParameters,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSnapshot,
    AimbatEventParametersSnapshot,
    AimbatSeismogramParametersSnapshot,
)
from pysmo.tools.utils import uuid_shortener as _uuid_shortener
from dataclasses import dataclass
from datetime import datetime
from sqlmodel import Session, select
from typing import Any
from uuid import UUID
from rich import box
from rich.table import Table


def string_to_uuid(
    session: Session,
    id: str,
    aimbat_class: type[
        AimbatDataSource
        | AimbatStation
        | AimbatEvent
        | AimbatEventParameters
        | AimbatSeismogram
        | AimbatSeismogramParameters
        | AimbatSnapshot
        | AimbatEventParametersSnapshot
        | AimbatSeismogramParametersSnapshot
    ],
    custom_error: str | None = None,
) -> UUID:
    """Determine a UUID from a string containing the first few characters.

    Args:
        session: Database session.
        id: Input string to find UUID for.
        aimbat_class: Aimbat class to use to find UUID.
        custom_error: Overrides the default error message.

    Returns:
        The full UUID.

    Raises:
        ValueError: If the UUID could not be determined.
    """
    uuid_set = {
        u for u in session.exec(select(aimbat_class.id)).all() if str(u).startswith(id)
    }
    if len(uuid_set) == 1:
        return uuid_set.pop()
    if len(uuid_set) == 0:
        raise ValueError(
            custom_error or f"Unable to find {aimbat_class.__name__} using id: {id}."
        )
    raise ValueError(f"Found more than one {aimbat_class.__name__} using id: {id}")


def uuid_shortener(
    session: Session,
    aimbat_obj: AimbatTypes,
    min_length: int = settings.min_id_length,
) -> str:
    uuids = session.exec(select(aimbat_obj.__class__.id)).all()
    uuid_dict = _uuid_shortener(uuids, min_length)
    reverse_uuid_dict = {v: k for k, v in uuid_dict.items()}
    return reverse_uuid_dict[aimbat_obj.id]


# -------------------------------------------------
# Styling
# -------------------------------------------------


@dataclass
class CliHints:
    """Hints for error messages."""

    ACTIVATE_EVENT = "Hint: activate an event with `aimbat event activate <EVENT_ID>`."
    LIST_EVENTS = "Hint: view available events with `aimbat event list`."


HINTS = CliHints()


@dataclass
class TableStyling:
    """This class is to set the colour of the table columns and elements."""

    id: str = "bright_blue"
    mine: str = "cyan"
    linked: str = "magenta"
    parameters: str = "green"

    @staticmethod
    def bool_formatter(true_or_false: bool | Any) -> str:
        if true_or_false is True:
            return "[bold green]:heavy_check_mark:[/]"
        elif true_or_false is False:
            return "[bold red]:heavy_multiplication_x:[/]"
        return true_or_false

    @staticmethod
    def datetime_formatter(dt: datetime, short: bool) -> str:
        if short:
            return dt.strftime("%Y-%m-%d [light_sea_green]%H:%M:%S[/]")
        return str(dt)


TABLE_STYLING = TableStyling()


def make_table(title: str | None = None) -> Table:
    table = Table(
        title=title,
        box=box.ROUNDED,
        expand=False,
        # row_styles=["dim", ""],
        border_style="dim",
        # highlight=True,
    )
    return table
