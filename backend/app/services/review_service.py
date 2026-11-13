"""Review service (Req 14, 40.7)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_customer_order
from app.core.errors import ConflictError, NotFoundError
from app.models import OrderStatus, Review, User
from app.schemas.review import ReviewIn

_INT32_MAX = 2**31 - 1


def create_review(db: Session, customer: User, order_id: int, payload: ReviewIn) -> Review:
    if not 0 < order_id <= _INT32_MAX:
        raise NotFoundError("Order not found")
    order = get_customer_order(db, order_id, customer.id)
    if order.status not in (OrderStatus.DELIVERED, OrderStatus.REFUNDED):
        raise ConflictError("Only delivered or refunded orders can be reviewed")
    if db.scalar(select(Review.id).where(Review.order_id == order.id)) is not None:
        raise ConflictError("This order has already been reviewed")
    review = Review(
        order_id=order.id,
        customer_id=customer.id,
        restaurant_id=order.restaurant_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    try:
        with db.begin_nested():
            db.add(review)
            db.flush()
    except IntegrityError:
        raise ConflictError("This order has already been reviewed") from None
    return review
