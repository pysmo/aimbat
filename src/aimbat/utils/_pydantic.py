from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ValidationError

__all__ = ["format_validation_error", "get_title_map"]


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


@lru_cache(maxsize=None)
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
