"""JSON utilities for AIMBAT."""

from typing import Any, Callable
from rich.console import Console
from ._style import make_table

__all__ = ["json_to_table"]


def json_to_table(
    data: dict[str, Any] | list[dict[str, Any]],
    title: str | None = None,
    formatters: dict[str, Callable[[Any], str]] | None = None,
    skip_keys: list[str] | None = None,
    column_order: list[str] | None = None,
    column_kwargs: dict[str, dict[str, Any]] | None = None,
    common_column_kwargs: dict[str, Any] | None = None,
) -> None:
    """Print a JSON dict or list of dicts as a rich table.

    For a single dict the table has ``Key`` and ``Value`` columns with one row
    per key-value pair.  For a list of dicts the keys become column headers and
    each list item becomes a row.

    Args:
        data: A single JSON dict or a list of JSON dicts.
        title: Optional title displayed above the table.
        formatters: Optional mapping of key names to callables that receive the
            raw value and return a string for display.
        skip_keys: Optional list of keys to exclude from the table.
        column_order: Optional list of keys defining the display order.  Keys
            not listed are appended after in their original order.  For a single
            dict this controls row order; for a list of dicts it controls column
            order.
        column_kwargs: Optional mapping of key names to keyword arguments
            forwarded to ``Table.add_column`` (e.g. ``style``, ``justify``,
            ``min_width``).  A ``"header"`` entry overrides the displayed column
            header name.  For a single dict the special keys ``"Key"`` and
            ``"Value"`` target those header columns.
        common_column_kwargs: Optional keyword arguments applied to every
            column, merged with any per-column entries in ``column_kwargs``.
            Per-column values take precedence over these defaults.

    Examples:
        >>> json_to_table({"name": "Alice", "age": 30}, title="Person")
        >>> json_to_table([{"id": 1}, {"id": 2}], formatters={"id": str})
        >>> json_to_table({"name": "Alice", "secret": "x"}, skip_keys=["secret"])
        >>> json_to_table(
        ...     [{"id": 1, "name": "Alice"}],
        ...     column_order=["name", "id"],
        ...     column_kwargs={"id": {"justify": "right", "style": "cyan"}},
        ... )
    """
    formatters = formatters or {}
    skip = set(skip_keys or [])
    column_kwargs = column_kwargs or {}
    common_column_kwargs = common_column_kwargs or {}
    console = Console()
    table = make_table(title=title)

    def _sorted_keys(keys: list[str]) -> list[str]:
        """Return keys reordered by column_order, with remaining keys appended."""
        if not column_order:
            return keys
        ordered = [k for k in column_order if k in keys]
        rest = [k for k in keys if k not in set(column_order)]
        return ordered + rest

    if isinstance(data, dict):
        key_kw = {**common_column_kwargs, **column_kwargs.get("Key", {})}
        val_kw = {**common_column_kwargs, **column_kwargs.get("Value", {})}
        table.add_column(key_kw.pop("header", "Key"), **key_kw)
        table.add_column(val_kw.pop("header", "Value"), **val_kw)
        keys = _sorted_keys([k for k in data if k not in skip])
        for key in keys:
            formatted = (
                formatters[key](data[key]) if key in formatters else str(data[key])
            )
            table.add_row(str(key), formatted)
    else:
        if not data:
            console.print(table)
            return
        columns = _sorted_keys([k for k in data[0].keys() if k not in skip])
        for col in columns:
            col_kw = {**common_column_kwargs, **column_kwargs.get(col, {})}
            table.add_column(col_kw.pop("header", str(col)), **col_kw)
        for item in data:
            row = []
            for col in columns:
                value = item.get(col)
                formatted = formatters[col](value) if col in formatters else str(value)
                row.append(formatted)
            table.add_row(*row)

    console.print(table)
