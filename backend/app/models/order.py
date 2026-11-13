from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import OrderStatus, PaymentStatus, ReturnStatus

if TYPE_CHECKING:
    from app.models.order_item import OrderItem
    from app.models.payment_ledger import PaymentLedger
    from app.models.restaurant import Restaurant
    from app.models.review import Review
    from app.models.user import User


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (CheckConstraint("total_amount >= 0", name="ck_orders_total_amount_nonneg"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="RESTRICT"), index=True
    )
    delivery_partner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="order_status"), index=True, default=OrderStatus.PLACED
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    delivery_address: Mapped[str] = mapped_column(String(300))
    delivery_phone: Mapped[str] = mapped_column(String(20))
    payment_status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status"), default=PaymentStatus.pending
    )
    return_status: Mapped[ReturnStatus] = mapped_column(
        SAEnum(ReturnStatus, name="return_status"), default=ReturnStatus.none, index=True
    )
    return_reason: Mapped[str | None] = mapped_column(Text)
    return_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    status_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped[User] = relationship(foreign_keys=[customer_id])
    delivery_partner: Mapped[User | None] = relationship(foreign_keys=[delivery_partner_id])
    restaurant: Mapped[Restaurant] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OrderItem.id",
    )
    ledger_entries: Mapped[list[PaymentLedger]] = relationship(
        back_populates="order", order_by="PaymentLedger.id"
    )
    review: Mapped[Review | None] = relationship(back_populates="order", uselist=False)
