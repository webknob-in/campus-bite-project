"""Reminder generation and resolution (Req 31).

``generate_reminders`` flags PLACED/ACCEPTED Orders not updated within the threshold.
``resolve_for_order`` is used by the order state machine so every status change clears the
Order's open Reminders (Req 31.4).
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models.admin_reminder_log import AdminReminderLog
from app.models.enums import OrderStatus
from app.models.order import Order

logger = logging.getLogger(__name__)

STALE_STATUSES = [OrderStatus.PLACED, OrderStatus.ACCEPTED]


def generate_reminders(db: Session, now: datetime, threshold_minutes: int) -> int:
    """Insert one Reminder per stale Order and status; return the number of new rows."""
    cutoff = now - timedelta(minutes=threshold_minutes)
    stale = db.execute(
        select(Order.id, Order.restaurant_id, Order.status, Order.status_updated_at).where(
            Order.status.in_(STALE_STATUSES), Order.status_updated_at < cutoff
        )
    ).all()
    if not stale:
        return 0
    rows = [
        {
            "order_id": o.id,
            "restaurant_id": o.restaurant_id,
            "status_at_reminder": o.status,
            "message": f"Order #{o.id} has been {o.status.value} for "
            f"{int((now - o.status_updated_at).total_seconds() // 60)} minutes",
            "is_resolved": False,
            "created_at": now,
        }
        for o in stale
    ]
    stmt = pg_insert(AdminReminderLog).values(rows).on_conflict_do_nothing(
        index_elements=["order_id", "status_at_reminder"]
    )
    # rowcount is unreliable for multi-row INSERT ... ON CONFLICT; count RETURNING rows instead.
    return len(db.execute(stmt.returning(AdminReminderLog.id)).all())


def run_reminders_job() -> None:
    """Scheduler/background entry point: own session, never raises."""
    try:
        with SessionLocal() as db:
            count = generate_reminders(
                db, utcnow(), get_settings().reminder_threshold_minutes
            )
            db.commit()
        logger.info("reminder job created %d reminder(s)", count)
    except Exception:
        logger.exception("reminder job failed")


def resolve_for_order(db: Session, order_id: int) -> int:
    """Mark every unresolved Reminder of the Order as resolved; return the rows updated."""
    result = db.execute(
        update(AdminReminderLog)
        .where(AdminReminderLog.order_id == order_id, AdminReminderLog.is_resolved.is_(False))
        .values(is_resolved=True)
    )
    return result.rowcount or 0
