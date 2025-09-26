from rich.table import Table
from rich import box
from dataclasses import dataclass


@dataclass
class TableColours:
    """This class is to set the colour of the table columns."""

    id: str = "bright_blue"
    mine: str = "cyan"
    linked: str = "magenta"
    parameters: str = "green"


TABLE_COLOURS = TableColours()


def make_table(title: str | None = None) -> Table:
    table = Table(
        title=title,
        box=box.ROUNDED,
        expand=False,
        # row_styles=["dim", ""],
        border_style="dim",
    )
    return table
