import types
from datetime import datetime
from typing import (
    Annotated,
    Any,
    TypeAliasType,
    Union,
    get_args,
    get_origin,
)

from pandas import NaT, Timedelta, Timestamp, to_datetime
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from aimbat.models import RichColSpec
from aimbat.utils.formatters import fmt_bool, fmt_float, fmt_timedelta, fmt_timestamp

__all__ = ["json_to_table"]

_MISSING_MARKER = " — "


def _justify_for_annotation(annotation: Any) -> str | None:
    """Infer a default column justification from a field's type annotation.

    Fully unwraps `X | None` unions, `Annotated[X, ...]` layers, and PEP 695
    `type` aliases (`TypeAliasType`) before checking the concrete type. Returns
    `"right"` for numeric and Timedelta types, `"center"` for booleans, and
    `None` for everything else (letting Rich use its default of left-aligned).
    """
    while True:
        origin = get_origin(annotation)
        if origin is Union or origin is types.UnionType:
            non_none = [a for a in get_args(annotation) if a is not type(None)]
            annotation = non_none[0] if len(non_none) == 1 else annotation
        elif origin is Annotated:
            annotation = get_args(annotation)[0]
        elif isinstance(annotation, TypeAliasType):
            annotation = annotation.__value__
        else:
            break

    if isinstance(annotation, type):
        if issubclass(annotation, bool):
            return "center"
        if issubclass(annotation, (int, float, Timedelta)):
            return "right"
    return None


def json_to_table(
    data: dict[str, Any] | list[dict[str, Any]],
    model: type[BaseModel],
    title: str | None = None,
    raw: bool = False,
    col_specs: dict[str, RichColSpec] | None = None,
    column_order: list[str] | None = None,
    key_header: str = "Property",
    value_header: str = "Value",
) -> None:
    """Print a JSON dict or list of dicts as a rich table driven by a Pydantic model.

    Args:
        data: A single row (dict) or list of rows to display.
        model: Pydantic model whose field metadata drives column configuration.
        title: Optional table title.
        raw: If `True`, ignore `RichColSpec` metadata and render using only
            type-based heuristics. Useful for a quick unformatted view.
        col_specs: Optional per-field overrides. Each entry is merged on top of
            the spec derived from the model field, so only the attributes that
            differ need to be set. Ignored when `raw=True`.
        column_order: Optional list of field names that should appear first, in
            that order. Fields not listed appear after in model-declaration order.
        key_header: Header for the property-name column in vertical (dict) tables.
        value_header: Header for the value column in vertical (dict) tables.
    """
    console = Console()
    table = Table(title=title)

    data_list = [data] if isinstance(data, dict) else data
    if not data_list:
        console.print(table)
        return

    # Build specs from model field metadata (skipped in raw mode).
    specs: dict[str, RichColSpec] = {}
    if not raw:
        for name, field in model.model_fields.items():
            spec: RichColSpec | None = None
            # Pydantic Field uses json_schema_extra; SQLModel Field uses schema_extra
            # which spreads its keys directly into _attributes_set on the FieldInfo.
            for source in (
                field.json_schema_extra,
                getattr(field, "_attributes_set", None),
            ):
                if isinstance(source, dict):
                    candidate = source.get("rich")
                    if isinstance(candidate, RichColSpec):
                        spec = candidate
                        break
            specs[name] = spec if spec is not None else RichColSpec()

        # Apply caller-supplied overrides. model_fields_set tracks which fields
        # were explicitly provided, so only those replace the model-derived spec.
        if col_specs:
            for name, override in col_specs.items():
                base = specs.get(name, RichColSpec())
                specs[name] = base.model_copy(
                    update={k: getattr(override, k) for k in override.model_fields_set}
                )

    def _ordered(names: list[str]) -> list[str]:
        if not column_order:
            return names
        ordered = [n for n in column_order if n in names]
        rest = [n for n in names if n not in set(column_order)]
        return ordered + rest

    def _fmt_val(name: str, val: Any) -> str:
        if raw:
            return "" if val is None else str(val)
        if val is None or val is NaT:
            return _MISSING_MARKER
        spec = specs.get(name)
        if spec and spec.formatter:
            return spec.formatter(val)
        if isinstance(val, bool):
            return fmt_bool(val)
        if isinstance(val, float):
            return fmt_float(val)
        if isinstance(val, Timedelta):
            return fmt_timedelta(val)
        if isinstance(val, (Timestamp, datetime)):
            return fmt_timestamp(val)
        low_key = name.lower()
        if (
            isinstance(val, str)
            and val.strip()
            and any(k in low_key for k in ("time", "date", "modified"))
        ):
            try:
                dt = to_datetime(val)
                return fmt_timestamp(dt)
            except (ValueError, TypeError):
                return str(val)
        return str(val)

    field_names = _ordered(list(model.model_fields.keys()))

    if isinstance(data, dict):
        # Vertical table
        table.add_column(key_header, style="cyan")
        table.add_column(value_header)
        for name in field_names:
            if name not in data:
                continue
            spec = specs.get(name)
            if spec and spec.display_title:
                label = spec.display_title
            else:
                field = model.model_fields[name]
                label = field.title if field.title else name
            table.add_row(label, _fmt_val(name, data[name]))
    else:
        # Horizontal table — restrict to fields present in data.
        data_keys: set[str] = set()
        for item in data_list:
            data_keys.update(item.keys())
        visible_fields = [n for n in field_names if n in data_keys]

        for name in visible_fields:
            spec = specs.get(name)
            field = model.model_fields[name]
            header = (
                spec.display_title
                if spec and spec.display_title
                else field.title or name
            )
            kwargs: dict[str, Any] = {}
            default_justify = _justify_for_annotation(field.annotation)
            if default_justify:
                kwargs["justify"] = default_justify
            if spec:
                if spec.justify:
                    kwargs["justify"] = spec.justify
                if spec.style:
                    kwargs["style"] = spec.style
                if spec.no_wrap is not None:
                    kwargs["no_wrap"] = spec.no_wrap
                if spec.highlight is not None:
                    kwargs["highlight"] = spec.highlight
            table.add_column(header, **kwargs)

        for item in data:
            table.add_row(*[_fmt_val(n, item.get(n)) for n in visible_fields])

    console.print(table)
