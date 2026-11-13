"""Shared pagination helper (Req 27)."""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.schemas.common import PageParams


def paginate(db: Session, stmt: Select[Any], params: PageParams) -> dict[str, Any]:
    """Run ``stmt`` one page at a time and return ``{items, total, page, page_size}``.

    * ``total`` is ``COUNT(*)`` over the same filtered statement (ordering dropped),
      so it always matches the rows the unpaginated query would return.
    * ``items`` is the requested slice (``OFFSET``/``LIMIT``). The caller owns a
      deterministic ``ORDER BY`` (include a unique tie-breaker such as ``id``) so pages
      neither overlap nor skip rows.
    * Single-entity selects (``select(Order)``) yield a list of entities via
      ``scalars()``. Selects with several columns/entities (``select(Order, User.name)``
      or ``select(MenuItem.name, func.sum(...))``) yield a list of ``Row`` tuples.
      Callers wrap the items into response schemas and build the ``Page`` from the dict.
    """
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.execute(count_stmt).scalar_one()

    page_stmt = stmt.offset(params.offset).limit(params.page_size)
    result = db.execute(page_stmt)
    if _is_single_entity(stmt):
        items: list[Any] = list(result.scalars().all())
    else:
        items = list(result.all())

    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
    }


def _is_single_entity(stmt: Select[Any]) -> bool:
    """True when ``stmt`` selects exactly one ORM entity (not a bare column)."""
    descriptions = stmt.column_descriptions
    if len(descriptions) != 1:
        return False
    entity = descriptions[0].get("entity")
    return entity is not None and descriptions[0].get("expr") is entity
