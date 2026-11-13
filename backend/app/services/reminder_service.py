"""Reminder generation and resolution.

``generate_reminders`` is added in task 10.2. ``resolve_for_order`` is used by the order
state machine so every status change clears the Order's open Reminders (Req 31.4).
"""

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.admin_reminder_log import AdminReminderLog


def resolve_for_order(db: Session, order_id: int) -> int:
    """Mark every unresolved Reminder of the Order as resolved; return the rows updated."""
    result = db.execute(
        update(AdminReminderLog)
        .where(AdminReminderLog.order_id == order_id, AdminReminderLog.is_resolved.is_(False))
        .values(is_resolved=True)
    )
    return result.rowcount or 0
