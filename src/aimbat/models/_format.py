"""Column specification dataclasses and formatters for model field display metadata."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from aimbat.utils.formatters import Formatter

__all__ = ["RichColSpec", "TuiColSpec"]


class RichColSpec(BaseModel):
    """Display metadata for a model field rendered in a Rich table.

    Attach to a field via `json_schema_extra={"rich": RichColSpec(...)}`.
    Only attributes that differ from the field's defaults need to be set.

    Attributes:
        display_title: Override for the column header shown in the Rich table.
            If `None`, the field's `title` is used instead.
        justify: Horizontal alignment for cell values in this column.
            Maps to `rich.table.Column.justify`. If `None`, no explicit
            alignment is applied.
        style: Style string for the column (e.g. "bold magenta").
        no_wrap: If `True`, cell values in this column will not wrap.
        highlight: If `True`, enables Rich's automatic syntax highlighting for
            values in this column. If `False`, disables it. If `None`, no
            explicit setting is applied.
        formatter: Custom formatter for cell values. Called with the raw field
            value (guaranteed non-`None`) and must return a display string. If
            `None`, a generic fallback is used instead.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    display_title: str | None = None
    justify: Literal["left", "center", "right"] | None = None
    style: str | None = None
    no_wrap: bool | None = None
    highlight: bool | None = True
    formatter: Callable[[Any], str] | None = None


@dataclass(frozen=True)
class TuiColSpec:
    """Display metadata for a model field rendered in the TUI.

    Attach to a field via `json_schema_extra={"tui": TuiColSpec(...)}`.
    Only attributes that differ from the field's defaults need to be set.

    Attributes:
        display_title: Override for the column header shown in the TUI table.
            If `None`, the field's `title` is used instead.
        text_align: Horizontal alignment for cell values in this column.
            Maps to `rich.text.Text.justify`. If `None`, no explicit alignment
            is applied and the DataTable renders with its default (left).
        formatter: Custom formatter for cell values. Called with the raw field
            value (guaranteed non-`None`) and must return a display string. If
            `None`, the generic `tui_fmt` fallback is used instead.
    """

    display_title: str | None = None
    text_align: Literal["left", "center", "right"] | None = None
    formatter: Formatter[Any] | None = None
