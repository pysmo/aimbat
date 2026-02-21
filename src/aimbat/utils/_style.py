"""AIMBAT styling."""

from dataclasses import dataclass
from pandas import Timestamp
from typing import Any
from rich import box
from rich.table import Table

__all__ = [
    "TableStyling",
    "make_table",
    "TABLE_STYLING",
]


@dataclass(frozen=True)
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
    def timestamp_formatter(dt: Timestamp, short: bool) -> str:
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
    )
    return table
