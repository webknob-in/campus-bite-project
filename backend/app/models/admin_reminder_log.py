from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import OrderStatus

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.restaurant import Restaurant


class AdminReminderLog(Base):
    """A Reminder flagging an Order stuck in PLACED or ACCEPTED past the threshold."""

    __tablename__ = "admin_reminder_logs"
    __table_args__ = (
        # One Reminder per (Order, status it was stuck in); generation uses ON CONFLICT DO NOTHING.
        UniqueConstraint(
            "order_id", "status_at_reminder", name="uq_admin_reminder_logs_order_status"
        ),
        Index("ix_admin_reminder_logs_restaurant_resolved", "restaurant_id", "is_resolved"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    status_at_reminder: Mapped[OrderStatus] = mapped_column(SAEnum(OrderStatus, name="order_status"))
    message: Mapped[str] = mapped_column(String(300))
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    order: Mapped[Order] = relationship()
    restaurant: Mapped[Restaurant] = relationship()
