from typing import Any, cast

from sqlalchemy.orm import QueryableAttribute

__all__ = ["rel"]


def rel(attr: Any) -> QueryableAttribute[Any]:
    """Cast a SQLModel relationship attribute to `QueryableAttribute` for use with `selectinload`.

    SQLModel types relationship fields as their Python collection type (e.g. `list[Foo]`),
    but SQLAlchemy's `selectinload` expects a `QueryableAttribute`. This helper performs
    the cast to satisfy mypy without requiring per-call `# type: ignore` comments.
    """
    return cast(QueryableAttribute[Any], attr)
