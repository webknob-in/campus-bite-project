"""Table-driven Order_Status state machine (Req 22).

``TRANSITIONS`` is the single source of truth: every allowed ``(from, to)`` pair maps to the
one Actor that may perform it. Anything not in the table is rejected with a 409.
"""

from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session

from app.core.errors import InvalidTransitionError
from app.db.base import utcnow
from app.models.enums import OrderStatus
from app.models.order import Order
from app.services import reminder_service


class Actor(str, Enum):
    ORDER_CUSTOMER = "order_customer"  # the Customer who placed the Order
    RESTAURANT_OWNER = "restaurant_owner"  # owner of the Order's Restaurant
    ASSIGNED_PARTNER = "assigned_partner"  # partner assigned to the Order


S = OrderStatus
TRANSITIONS: dict[tuple[OrderStatus, OrderStatus], Actor] = {
    (S.PLACED, S.CANCELLED): Actor.ORDER_CUSTOMER,
    (S.PLACED, S.ACCEPTED): Actor.RESTAURANT_OWNER,
    (S.ACCEPTED, S.PREPARING): Actor.RESTAURANT_OWNER,
    (S.PREPARING, S.READY): Actor.RESTAURANT_OWNER,
    (S.READY, S.ASSIGNED): Actor.RESTAURANT_OWNER,
    (S.ASSIGNED, S.OUT_FOR_DELIVERY): Actor.ASSIGNED_PARTNER,
    (S.OUT_FOR_DELIVERY, S.DELIVERED): Actor.ASSIGNED_PARTNER,
    (S.DELIVERED, S.REFUNDED): Actor.RESTAURANT_OWNER,
}
TERMINAL = {S.CANCELLED, S.REFUNDED}


def is_allowed(current: OrderStatus, target: OrderStatus, actor: Actor) -> bool:
    return TRANSITIONS.get((current, target)) == actor


def transition(
    db: Session, order: Order, target: OrderStatus, actor: Actor, now: datetime | None = None
) -> Order:
    """Move ``order`` to ``target`` if ``actor`` may do so, else raise ``InvalidTransitionError``.

    Does not commit; the caller owns the transaction.
    """
    if not is_allowed(order.status, target, actor):
        raise InvalidTransitionError(
            f"Cannot change order from {order.status.value} to {target.value}"
        )
    now = now or utcnow()
    order.status = target
    order.status_updated_at = now
    order.updated_at = now
    if target is S.DELIVERED:
        order.delivered_at = now
    reminder_service.resolve_for_order(db, order.id)  # Req 31.4
    return order
