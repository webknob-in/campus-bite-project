"""Restaurant statistics computed with SQL aggregates (Req 19, 37.10)."""

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.models import LedgerType, Order, OrderItem, OrderStatus, PaymentLedger, Review
from app.schemas.stats import StatsOut, TopDishOut

TOP_DISHES_LIMIT = 5


def restaurant_stats(db: Session, restaurant_id: int, now: datetime | None = None) -> StatsOut:
    """Statistics for one restaurant. ``now`` (UTC) defines "today" and is injectable for tests."""
    now = (now or utcnow()).astimezone(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    rows = db.execute(
        select(Order.status, func.count(Order.id)).where(Order.restaurant_id == restaurant_id).group_by(Order.status)
    ).all()
    status_counts = {s.value: 0 for s in OrderStatus}
    for status, count in rows:
        status_counts[status.value] = count
    total_orders = sum(status_counts.values())

    orders_today = db.scalar(
        select(func.count(Order.id)).where(
            Order.restaurant_id == restaurant_id, Order.created_at >= day_start, Order.created_at < day_end
        )
    ) or 0

    paid, refunded = db.execute(
        select(
            func.coalesce(func.sum(case((PaymentLedger.entry_type == LedgerType.PAYMENT, PaymentLedger.amount), else_=0)), 0),
            func.coalesce(func.sum(case((PaymentLedger.entry_type == LedgerType.REFUND, PaymentLedger.amount), else_=0)), 0),
        )
        .join(Order, Order.id == PaymentLedger.order_id)
        .where(Order.restaurant_id == restaurant_id)
    ).one()
    net_revenue = Decimal(paid) - Decimal(refunded)

    avg = db.scalar(select(func.avg(Review.rating)).where(Review.restaurant_id == restaurant_id))
    average_rating = float(Decimal(avg).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if avg is not None else None

    qty = func.sum(OrderItem.quantity)
    dishes = db.execute(
        select(OrderItem.name, qty.label("quantity"))
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.restaurant_id == restaurant_id)
        .group_by(OrderItem.name)
        .order_by(qty.desc(), OrderItem.name.asc())
        .limit(TOP_DISHES_LIMIT)
    ).all()

    return StatsOut(
        total_orders=total_orders,
        orders_today=orders_today,
        net_revenue=net_revenue,
        average_rating=average_rating,
        status_counts=status_counts,
        top_dishes=[TopDishOut(name=n, quantity=int(q)) for n, q in dishes],
    )
