"""Return service (Req 15, 40.8)."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.api.deps import get_customer_order, get_restaurant_order
from app.core.errors import ConflictError, NotFoundError
from app.db.base import utcnow
from app.models import LedgerType, Order, OrderStatus, PaymentLedger, PaymentStatus, ReturnStatus, User
from app.schemas.returns import ReturnIn
from app.services.order_state import Actor, transition

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


def _lock_requested(db: Session, restaurant_id: int, order_id: int) -> Order:
    if not 0 < order_id <= _INT32_MAX:
        raise NotFoundError("Order not found")
    order = get_restaurant_order(db, order_id, restaurant_id, for_update=True)
    if order.return_status != ReturnStatus.requested:
        raise ConflictError("This return request has already been decided or does not exist")
    return order


def approve_return(db: Session, restaurant_id: int, order_id: int) -> Order:
    """Refund a requested return: DELIVERED -> REFUNDED, approved, refunded, REFUND ledger row."""
    order = _lock_requested(db, restaurant_id, order_id)
    if order.status != OrderStatus.DELIVERED:
        raise ConflictError("Only delivered orders can be refunded")
    transition(db, order, OrderStatus.REFUNDED, Actor.RESTAURANT_OWNER)
    order.return_status = ReturnStatus.approved
    order.payment_status = PaymentStatus.refunded
    order.ledger_entries.append(
        PaymentLedger(
            order_id=order.id,
            entry_type=LedgerType.REFUND,
            amount=order.total_amount,
            status="success",
            transaction_ref=f"REFUND-{order.id}-{uuid4().hex[:16]}",
            card_last4=None,
            created_at=utcnow(),
        )
    )
    db.flush()
    return order


def reject_return(db: Session, restaurant_id: int, order_id: int) -> Order:
    order = _lock_requested(db, restaurant_id, order_id)
    order.return_status = ReturnStatus.rejected
    db.flush()
    return order
