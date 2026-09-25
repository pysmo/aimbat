from collections.abc import Sequence
from functools import cache
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

__all__ = [
    "check_field_name_flags",
    "dump_models",
    "format_validation_error",
    "get_title_map",
]


def format_validation_error(exc: ValidationError) -> str:
    """Format a `ValidationError` as a short, semicolon-joined message.

    Strips the redundant `"Value error, "` prefix Pydantic adds to custom
    validator messages, so the result is fit for display without leaking
    implementation detail.

    Args:
        exc: The validation error to format.

    Returns:
        A single-line, semicolon-joined summary of all validation errors.
    """
    return "; ".join(e["msg"].removeprefix("Value error, ") for e in exc.errors())


@cache
def get_title_map(model_class: type[BaseModel]) -> dict[str, str]:
    """Build a mapping from field names to their display titles.

    Includes both regular and computed fields. A field without a `title` set
    falls back to its name with underscores replaced by spaces.

    Args:
        model_class: Pydantic model class to inspect.

    Returns:
        Mapping of field name to display title.
    """
    mapping: dict[str, str] = {}

    for name, info in model_class.model_fields.items():
        mapping[name] = info.title or name.replace("_", " ")

    computed_fields: dict[str, Any] = getattr(
        model_class, "__pydantic_computed_fields__", {}
    )
    for name, info in computed_fields.items():
        title = getattr(info, "title", None)
        mapping[name] = title or name.replace("_", " ")

    return mapping


def check_field_name_flags(
    by_alias: bool, by_title: bool, from_read_model: bool | None = None
) -> None:
    """Check the field-naming flags the `dump_*_table` functions take.

    Args:
        by_alias: Whether serialisation aliases are to be used for the field names.
        by_title: Whether field title metadata is to be used for the field names.
        from_read_model: Whether the caller is dumping from its read model, for
            the functions that offer the choice. `None` for the ones that don't.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
        ValueError: If `by_title` is True but `from_read_model` is False.
    """
    if by_alias and by_title:
        raise ValueError("Arguments 'by_alias' and 'by_title' are mutually exclusive.")

    if from_read_model is False and by_title:
        raise ValueError("'by_title' is only supported when 'from_read_model' is True.")


def dump_models[T: BaseModel](
    records: Sequence[T],
    model_class: type[T],
    *,
    by_alias: bool = False,
    by_title: bool = False,
    exclude: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Serialise records to a JSON-compatible list of dicts.

    The shared tail of the `core.dump_*_table` functions: each builds its own
    query, and its read models where it has them, then hands the result here
    so field naming and exclusions are applied the same way everywhere.

    Args:
        records: Records to serialise, all instances of `model_class`.
        model_class: Class of the records, used for both the type adapter and
            the title map.
        by_alias: Whether to use serialisation aliases for the field names.
        by_title: Whether to use the field title metadata for the field names.
            Mutually exclusive with `by_alias`.
        exclude: Field names to exclude from every record.

    Returns:
        One dict per record.

    Raises:
        ValueError: If both `by_alias` and `by_title` are True.
    """
    check_field_name_flags(by_alias, by_title)

    exclude_spec: dict[str, set[str]] | None = {"__all__": exclude} if exclude else None

    adapter: TypeAdapter[Sequence[T]] = TypeAdapter(Sequence[model_class])  # type: ignore[valid-type]
    data: list[dict[str, Any]] = adapter.dump_python(
        records, mode="json", by_alias=by_alias, exclude=exclude_spec
    )

    if by_title:
        title_map = get_title_map(model_class)
        return [{title_map.get(k, k): v for k, v in row.items()} for row in data]

    return data
