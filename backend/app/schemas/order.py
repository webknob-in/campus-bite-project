"""Order request and response schemas (Req 11, 12, 23.4).

``MockPaymentIn`` holds the dummy card. The card number and CVV are excluded from ``repr`` and
are never copied anywhere by the services; only the last 4 digits reach the ledger (Req 11.10).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.base import utcnow
from app.models.enums import LedgerType, OrderStatus, PaymentStatus, ReturnStatus
from app.schemas.menu import Money

if TYPE_CHECKING:
    from app.models.order import Order

PHONE_PATTERN = r"^[0-9+\-\s]{7,20}$"
EXPIRY_PATTERN = r"^(0[1-9]|1[0-2])/\d{2}$"


class OrderItemIn(BaseModel):
    menu_item_id: int = Field(gt=0, strict=True)
    quantity: int = Field(ge=1, le=99, strict=True)


class MockPaymentIn(BaseModel):
    card_holder: str = Field(min_length=2, max_length=100)
    card_number: str = Field(pattern=r"^\d{16}$", repr=False)
    expiry: str = Field(pattern=EXPIRY_PATTERN)
    cvv: str = Field(pattern=r"^\d{3}$", repr=False)

    @field_validator("expiry")
    @classmethod
    def expiry_not_in_past(cls, value: str) -> str:
        """The card is valid through the end of its expiry month (same rule as the checkout form)."""
        month, year = int(value[:2]), 2000 + int(value[3:])
        now = utcnow()
        if (year, month) < (now.year, now.month):
            raise ValueError("Card has expired")
        return value


class OrderCreate(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)
    delivery_address: str = Field(min_length=5, max_length=300)
    delivery_phone: str = Field(pattern=PHONE_PATTERN)
    payment: MockPaymentIn


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int | None = None
    name: str
    unit_price: Money
    quantity: int
    line_total: Money


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_type: LedgerType
    amount: Money
    status: str
    transaction_ref: str
    card_last4: str | None = None
    created_at: datetime


class OrderReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rating: int
    comment: str | None = None
    created_at: datetime


class OrderOut(BaseModel):
    """An Order with its lines. Build it with ``OrderOut.from_order(order)``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    payment_status: PaymentStatus
    return_status: ReturnStatus
    total_amount: Money
    delivery_address: str
    delivery_phone: str
    restaurant_id: int
    restaurant_name: str
    items: list[OrderItemOut]
    created_at: datetime
    updated_at: datetime
    status_updated_at: datetime
    delivered_at: datetime | None = None

    @classmethod
    def from_order(cls, order: Order) -> OrderOut:
        return cls(**cls._fields(order))

    @staticmethod
    def _fields(order: Order) -> dict:
        return {
            "id": order.id,
            "status": order.status,
            "payment_status": order.payment_status,
            "return_status": order.return_status,
            "total_amount": order.total_amount,
            "delivery_address": order.delivery_address,
            "delivery_phone": order.delivery_phone,
            "restaurant_id": order.restaurant_id,
            "restaurant_name": order.restaurant.name,
            "items": [OrderItemOut.model_validate(i) for i in sorted(order.items, key=lambda i: i.id)],
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "status_updated_at": order.status_updated_at,
            "delivered_at": order.delivered_at,
        }


class OrderDetailOut(OrderOut):
    """``OrderOut`` plus return details, ledger entries, the Review and the partner's name (Req 12.2, 23.4)."""

    return_reason: str | None = None
    return_requested_at: datetime | None = None
    ledger_entries: list[LedgerEntryOut]
    review: OrderReviewOut | None = None
    delivery_partner_name: str | None = None

    @classmethod
    def from_order(cls, order: Order) -> OrderDetailOut:
        ledger = sorted(order.ledger_entries, key=lambda e: (e.created_at, e.id))
        return cls(
            **cls._fields(order),
            return_reason=order.return_reason,
            return_requested_at=order.return_requested_at,
            ledger_entries=[LedgerEntryOut.model_validate(e) for e in ledger],
            review=OrderReviewOut.model_validate(order.review) if order.review else None,
            delivery_partner_name=order.delivery_partner.name if order.delivery_partner else None,
        )
