"""Owner order management schemas (Req 17, 18)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.models.enums import OrderStatus, PaymentStatus, ReturnStatus
from app.schemas.menu import Money

if TYPE_CHECKING:
    from app.models.order import Order


class OwnerOrderItemOut(BaseModel):
    name: str
    quantity: int
    price: Money


class PartnerRefOut(BaseModel):
    id: int
    name: str


class OwnerOrderOut(BaseModel):
    id: int
    status: OrderStatus
    payment_status: PaymentStatus
    return_status: ReturnStatus
    total_amount: Money
    created_at: datetime
    status_updated_at: datetime
    customer_name: str
    delivery_address: str
    delivery_phone: str
    items: list[OwnerOrderItemOut]
    delivery_partner: PartnerRefOut | None = None

    @classmethod
    def from_order(cls, order: Order) -> OwnerOrderOut:
        partner = order.delivery_partner
        return cls(
            id=order.id,
            status=order.status,
            payment_status=order.payment_status,
            return_status=order.return_status,
            total_amount=order.total_amount,
            created_at=order.created_at,
            status_updated_at=order.status_updated_at,
            customer_name=order.customer.name,
            delivery_address=order.delivery_address,
            delivery_phone=order.delivery_phone,
            items=[
                OwnerOrderItemOut(name=i.name, quantity=i.quantity, price=i.unit_price)
                for i in sorted(order.items, key=lambda i: i.id)
            ],
            delivery_partner=PartnerRefOut(id=partner.id, name=partner.name) if partner else None,
        )


class OwnerStatusUpdate(BaseModel):
    status: OrderStatus


class AssignPartnerIn(BaseModel):
    delivery_partner_id: int = Field(strict=True)


class DeliveryPartnerOut(BaseModel):
    id: int
    name: str
    phone: str | None = None
