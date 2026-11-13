"""Delivery partner order schemas (Req 21)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.models.enums import OrderStatus
from app.schemas.menu import Money

if TYPE_CHECKING:
    from app.models.order import Order


class PartnerOrderItemOut(BaseModel):
    name: str
    quantity: int
    price: Money


class PartnerOrderOut(BaseModel):
    id: int
    status: OrderStatus
    customer_name: str
    delivery_phone: str
    delivery_address: str
    restaurant_name: str
    restaurant_address: str
    items: list[PartnerOrderItemOut]
    total_amount: Money
    created_at: datetime
    status_updated_at: datetime
    delivered_at: datetime | None = None

    @classmethod
    def from_order(cls, order: Order) -> PartnerOrderOut:
        return cls(
            id=order.id,
            status=order.status,
            customer_name=order.customer.name,
            delivery_phone=order.delivery_phone,
            delivery_address=order.delivery_address,
            restaurant_name=order.restaurant.name,
            restaurant_address=order.restaurant.address,
            items=[
                PartnerOrderItemOut(name=i.name, quantity=i.quantity, price=i.unit_price)
                for i in sorted(order.items, key=lambda i: i.id)
            ],
            total_amount=order.total_amount,
            created_at=order.created_at,
            status_updated_at=order.status_updated_at,
            delivered_at=order.delivered_at,
        )


class PartnerStatusUpdate(BaseModel):
    status: OrderStatus
