from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import LedgerType

if TYPE_CHECKING:
    from app.models.order import Order


class PaymentLedger(Base):
    """One money movement for an Order. A ``REFUND`` entry is the refund record."""

    __tablename__ = "payment_ledger"
    __table_args__ = (UniqueConstraint("transaction_ref", name="uq_payment_ledger_transaction_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), index=True)
    entry_type: Mapped[LedgerType] = mapped_column(SAEnum(LedgerType, name="ledger_type"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20))
    transaction_ref: Mapped[str] = mapped_column(String(40))
    card_last4: Mapped[str | None] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    order: Mapped[Order] = relationship(back_populates="ledger_entries")
