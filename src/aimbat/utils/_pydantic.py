from functools import lru_cache
from typing import Any

from pydantic import BaseModel

__all__ = ["get_title_map"]


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
