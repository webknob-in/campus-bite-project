"""Shared Order filters for the customer, owner and partner list endpoints (Req 24.2, 24.3).

Dates are ISO dates interpreted in UTC: ``date_from`` is inclusive from 00:00 and ``date_to`` is
inclusive through the end of that day (``created_at < date_to + 1 day``).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy import Select

from app.models.enums import OrderStatus
from app.models.order import Order


def _check_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "date_from"),
                    "msg": "date_from must be on or before date_to",
                    "input": date_from.isoformat(),
                }
            ]
        )


def apply_order_filters(
    stmt: Select,
    status: OrderStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Select:
    """Add the ``status`` / ``created_at`` range conditions to a select over ``Order``.

    Raises ``RequestValidationError`` (HTTP 422) when ``date_from`` is after ``date_to``.
    """
    _check_date_range(date_from, date_to)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    if date_from is not None:
        stmt = stmt.where(Order.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to is not None and date_to < date.max:
        end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        stmt = stmt.where(Order.created_at < end)
    return stmt


class OrderFilterParams:
    """``status``, ``date_from`` and ``date_to`` query parameters. Use as ``Depends()``.

    An invalid enum value or date is a 422 from FastAPI; ``date_from > date_to`` is a 422 too.
    """

    def __init__(
        self,
        status: Annotated[OrderStatus | None, Query(description="Only Orders with this status.")] = None,
        date_from: Annotated[date | None, Query(description="Created on or after this UTC date.")] = None,
        date_to: Annotated[date | None, Query(description="Created on or before this UTC date.")] = None,
    ) -> None:
        _check_date_range(date_from, date_to)
        self.status = status
        self.date_from = date_from
        self.date_to = date_to

    def apply(self, stmt: Select) -> Select:
        return apply_order_filters(stmt, self.status, self.date_from, self.date_to)
