import math
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping, NamedTuple

from pandas import NaT, Timestamp, to_datetime
from rich.console import Console
from rich.table import Table

__all__ = "FormatResult", "TABLE_STYLING", "json_to_table"


class FormatResult(NamedTuple):
    """Container for a formatted value and its display metadata."""

    text: str
    justify: str = "left"
    style: str | None = None


@dataclass(frozen=True)
class TableStyling:
    """Class to set the colour and formatting of table elements."""

    ID: str = "yellow"
    linked: str = "magenta"
    mine: str = "cyan"
    parameters: str = "green"

    @staticmethod
    def flip_formatter(val: bool | Any) -> FormatResult:
        if val is True:
            return FormatResult("[bold yellow]:up-down_arrow:[/]", justify="center")
        elif val is False:
            return FormatResult("", justify="center")
        return FormatResult(str(val))

    @staticmethod
    def bool_formatter(val: bool | Any) -> FormatResult:
        if val is None:
            return FormatResult("", justify="center")
        if val is True:
            return FormatResult("[bold green]:heavy_check_mark:[/]", justify="center")
        elif val is False:
            return FormatResult(
                "[bold red]:heavy_multiplication_x:[/]", justify="center"
            )
        return FormatResult(str(val))

    @staticmethod
    def float_formatter(value: float | Any, short: bool = True) -> FormatResult:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return FormatResult("—", justify="right")
        text = f"{value:.3f}" if short and isinstance(value, float) else str(value)
        return FormatResult(text, justify="right")

    @staticmethod
    def timestamp_formatter(dt: Any, short: bool = True) -> FormatResult:
        if isinstance(dt, str) and dt.strip():
            try:
                dt = to_datetime(dt)
            except (ValueError, TypeError):
                return FormatResult(str(dt), justify="left")

        if dt is NaT or dt is None or dt == "":
            return FormatResult("—", justify="left")

        if not hasattr(dt, "strftime"):
            return FormatResult(str(dt) if dt is not None else "—")

        text = dt.strftime("%Y-%m-%d %H:%M:%S") if short else str(dt)
        return FormatResult(text, justify="left", style="italic")

    @staticmethod
    def default_formatter(val: Any) -> FormatResult:
        """Fallback formatter for strings and other types."""
        if val is None or val is NaT or val == "":
            return FormatResult("—")

        text = str(val)
        justify = "right" if text.isdigit() else "left"
        return FormatResult(text, justify=justify)

    @staticmethod
    def short_id_formatter(val: Any) -> FormatResult:
        """Formatter for short ID columns."""
        if val is None or val is NaT or val == "":
            return FormatResult("—")
        return FormatResult(str(val), style="yellow")


TABLE_STYLING = TableStyling()


def json_to_table(
    data: dict[str, Any] | list[dict[str, Any]],
    title: str | None = None,
    formatters: Mapping[str, Callable[[Any], str | FormatResult]] | None = None,
    skip_keys: list[str] | None = None,
    column_order: list[str] | None = None,
    column_kwargs: Mapping[str, Mapping[str, Any]] | None = None,
    common_column_kwargs: Mapping[str, Any] | None = None,
    short: bool = True,
) -> None:
    """
    Print a JSON dict or list of dicts as a rich table.
    Headers are kept as-is from keys unless renamed via column_kwargs.
    """
    formatters = formatters or {}
    skip = set(skip_keys or [])
    column_kwargs = column_kwargs or {}
    common_column_kwargs = common_column_kwargs or {}
    console = Console()
    table = Table(title=title)

    styling_keys = {f.name for f in fields(TableStyling)}

    def _sorted_keys(keys: Iterable[str]) -> list[str]:
        keys_list = list(keys)
        if not column_order:
            return keys_list
        ordered = [k for k in column_order if k in keys_list]
        rest = [k for k in keys_list if k not in set(column_order)]
        return ordered + rest

    def _get_formatted(key: str, val: Any) -> FormatResult:
        """Resolves formatting and ensures a FormatResult is always returned."""
        raw_result: str | FormatResult | None = None

        if key in formatters:
            raw_result = formatters[key](val)

        if raw_result is None:
            low_key = key.lower()

            if isinstance(val, bool):
                raw_result = TABLE_STYLING.bool_formatter(val)
            elif isinstance(val, float):
                raw_result = TABLE_STYLING.float_formatter(val, short=short)
            elif isinstance(val, (Timestamp, datetime)):
                raw_result = TABLE_STYLING.timestamp_formatter(val, short=short)
            elif (
                isinstance(val, str)
                and val.strip()
                and any(k in low_key for k in ("time", "date", "modified"))
            ):
                raw_result = TABLE_STYLING.timestamp_formatter(val, short=short)
            else:
                raw_result = TABLE_STYLING.default_formatter(val)

        return (
            raw_result
            if isinstance(raw_result, FormatResult)
            else FormatResult(str(raw_result))
        )

    def _add_column_to_table(key: str, default_header: str) -> None:
        specific_kwargs = dict(column_kwargs.get(key, {}))
        kwargs = {**common_column_kwargs, **specific_kwargs}
        header = kwargs.pop("header", default_header)

        low_key = key.lower()
        is_short_id = "short" in low_key and ("_id" in low_key or " id" in low_key)
        is_exact_id = low_key == "id"

        if is_short_id or is_exact_id:
            for sep in ("_", " "):
                search = f"short{sep}id"
                if low_key == search:
                    header = "ID"
                    kwargs.setdefault("style", "yellow")
                    break
                sep_idx = low_key.find(f"short{sep}")
                id_idx = low_key.find("id")
                if sep_idx >= 0 and id_idx > sep_idx + 6:
                    middle = key[sep_idx + 6 : id_idx].strip("_").strip()
                    if middle:
                        header = f"{middle.title()} ID"
                        kwargs.setdefault("style", "magenta")
                    else:
                        header = "ID"
                        kwargs.setdefault("style", "yellow")
                    break
            else:
                header = "ID"
                kwargs.setdefault("style", "yellow")
            kwargs.setdefault("highlight", False)
            kwargs.setdefault("no_wrap", True)
        elif low_key.endswith("_id") or low_key.endswith(" id"):
            middle = ""
            for suffix in ("_id", " id"):
                if low_key.endswith(suffix):
                    middle = key[: -len(suffix)].strip("_").strip()
                    break
            if middle:
                header = f"{middle.title()} ID"
                kwargs.setdefault("style", "magenta")
            else:
                header = "ID"
                kwargs.setdefault("style", "yellow")
            kwargs.setdefault("highlight", False)
            kwargs.setdefault("no_wrap", True)

        hints = FormatResult("")

        if isinstance(data, dict):
            hints = _get_formatted(key, data.get(key))
        elif data:
            for item in data:
                val = item.get(key)
                if (
                    val is not None
                    and val is not NaT
                    and (not isinstance(val, str) or val.strip() != "")
                ):
                    hints = _get_formatted(key, val)
                    break

        if "style" not in kwargs and key in styling_keys:
            kwargs["style"] = getattr(TABLE_STYLING, key)

        if "highlight" not in kwargs:
            kwargs["highlight"] = not is_short_id

        if "justify" not in kwargs:
            kwargs["justify"] = hints.justify
        if "style" not in kwargs and hints.style:
            kwargs["style"] = hints.style

        table.add_column(header, **kwargs)

    if isinstance(data, dict):
        _add_column_to_table("Key", "Key")
        _add_column_to_table("Value", "Value")
        keys = _sorted_keys([k for k in data if k not in skip])
        for key in keys:
            res = _get_formatted(key, data[key])
            table.add_row(str(key), res.text)
    else:
        if not data:
            console.print(table)
            return
        columns = _sorted_keys([k for k in data[0].keys() if k not in skip])
        for col in columns:
            _add_column_to_table(col, str(col))
        for item in data:
            row_cells = [_get_formatted(col, item.get(col)).text for col in columns]
            table.add_row(*row_cells)

    console.print(table)
