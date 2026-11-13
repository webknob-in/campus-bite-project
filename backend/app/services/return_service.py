"""Return service (Req 15, 40.8)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.deps import get_customer_order
from app.core.errors import ConflictError, NotFoundError
from app.db.base import utcnow
from app.models import Order, OrderStatus, ReturnStatus, User
from app.schemas.returns import ReturnIn

_INT32_MAX = 2**31 - 1


def request_return(db: Session, customer: User, order_id: int, payload: ReturnIn) -> Order:
    if not 0 < order_id <= _INT32_MAX:
        raise NotFoundError("Order not found")
    order = get_customer_order(db, order_id, customer.id, for_update=True)
    if order.status != OrderStatus.DELIVERED:
        raise ConflictError("Only delivered orders can be returned")
    if order.return_status != ReturnStatus.none:
        raise ConflictError("A return was already requested for this order")
    order.return_status = ReturnStatus.requested
    order.return_reason = payload.reason
    order.return_requested_at = utcnow()
    db.flush()
    return order
