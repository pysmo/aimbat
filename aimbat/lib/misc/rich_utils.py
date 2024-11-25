from rich.table import Table
from rich import box


def make_table(title: str | None = None) -> Table:
    table = Table(
        title=title,
        box=box.ROUNDED,
        expand=False,
        row_styles=["dim", ""],
        border_style="dim",
    )
    return table
