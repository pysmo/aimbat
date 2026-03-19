"""Shared formatting helpers for TUI tables."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from pandas import Timedelta
from pydantic import BaseModel
from rich.text import Text

from aimbat.models._format import TuiColSpec
from aimbat.utils.formatters import fmt_bool, fmt_float

if TYPE_CHECKING:
    from aimbat.core import FieldGroup

__all__ = [
    "fmt_float_sem",
    "fmt_groups",
    "fmt_td_sem",
    "fmt_val",
    "tui_cell",
    "tui_display_title",
    "tui_fmt",
]


def tui_display_title(model: type[BaseModel], field_name: str) -> str:
    """Return the TUI display title for a model field.

    Reads `TuiColSpec.display_title` from `json_schema_extra` if present,
    otherwise falls back to the field's `title` or a humanised field name.
    """
    info = model.model_fields.get(field_name)
    if info is None:
        return field_name.replace("_", " ")
    extra = info.json_schema_extra
    if isinstance(extra, dict):
        col_spec = extra.get("tui")
        if isinstance(col_spec, TuiColSpec) and col_spec.display_title is not None:
            return col_spec.display_title
    return info.title or field_name.replace("_", " ")


def fmt_float_sem(v: float | None, sem: float | None, decimals: int = 4) -> str:
    """Format a float with an optional SEM as `value ± sem`, or `—` if None."""
    if v is None:
        return "—"
    if sem is not None:
        return f"{v:.{decimals}f} ± {sem:.{decimals}f}"
    return f"{v:.{decimals}f}"


def fmt_td_sem(td: Timedelta | None, sem: Timedelta | None, decimals: int = 5) -> str:
    """Format a Timedelta in seconds with an optional SEM, or `—` if None."""
    if td is None:
        return "—"
    s = f"{td.total_seconds():.{decimals}f}"
    if sem is not None:
        s += f" ± {sem.total_seconds():.{decimals}f}"
    return s + " s"


def fmt_val(val: object, sem: object = None) -> str:
    """Format a model field value for display in a quality panel.

    Dispatches to `fmt_float_sem` or `fmt_td_sem` for numeric types so that an
    optional `sem` sibling is rendered as `value ± sem`. Booleans render as ✓/✗.
    Returns `—` for None."""
    if val is None:
        return "—"
    if isinstance(val, bool):
        return "✓" if val else "✗"
    if isinstance(val, Timedelta):
        return fmt_td_sem(val, sem if isinstance(sem, Timedelta) else None)
    if isinstance(val, float):
        return fmt_float_sem(val, sem if isinstance(sem, float) else None)
    return str(val)


def fmt_groups(
    groups: list[FieldGroup],
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Format a list of `FieldGroup` instances for `QualityModal`.

    Returns a list of `(group_title, rows)` pairs, skipping groups with no
    content. Each `rows` element is a pre-formatted `(label, value)` pair.
    """
    result = []
    for group in groups:
        rows: list[tuple[str, str]] = []
        if group.fields:
            rows = [
                (spec.title, fmt_val(spec.value, spec.sem)) for spec in group.fields
            ]
        elif group.empty_message:
            rows = [(group.empty_message, "")]
        if rows:
            result.append((group.title, rows))
    return result


@lru_cache(maxsize=None)
def _col_spec_map(model: type[BaseModel]) -> dict[str, TuiColSpec]:
    """Return a map of Pydantic field title → `TuiColSpec` for fields that carry one."""
    result: dict[str, TuiColSpec] = {}
    for name, info in model.model_fields.items():
        extra = info.json_schema_extra
        if isinstance(extra, dict):
            col_spec = extra.get("tui")
            if isinstance(col_spec, TuiColSpec):
                title = info.title or name.replace("_", " ")
                result[title] = col_spec
    return result


def tui_cell(model: type[BaseModel], title: str, val: object) -> str | Text:
    """Format a model field value for a DataTable cell.

    If the field's `TuiColSpec` specifies a `formatter`, it is called with the
    raw value (after None is handled). Otherwise delegates to `tui_fmt`. Wraps
    the result in `rich.text.Text` when `text_align` is set.
    """
    col_spec = _col_spec_map(model).get(title)
    if val is None:
        formatted = "—"
    elif col_spec and col_spec.formatter is not None:
        formatted = col_spec.formatter(val)
    else:
        formatted = tui_fmt(val)
    if col_spec and col_spec.text_align:
        return Text(formatted, justify=col_spec.text_align)
    return formatted


def tui_fmt(val: object) -> str:
    """Format a raw field value for display in a Textual DataTable cell.

    Applies generic type-based rules (bool via ``fmt_bool``, float via
    ``fmt_float``, ISO timestamp truncation) before falling back to ``str``.
    Field-specific formatting should be handled via ``TuiColSpec.formatter``
    instead. Returns ``—`` for ``None``."""
    if val is None:
        return "—"
    if isinstance(val, bool):
        return fmt_bool(val)
    if isinstance(val, float):
        return fmt_float(val)
    if isinstance(val, int):
        return str(val)
    if isinstance(val, str) and "T" in val and len(val) >= 19:
        return val[:19]
    return str(val)
