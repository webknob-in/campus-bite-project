"""Return request schemas (Req 15)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.enums import OrderStatus, PaymentStatus, ReturnStatus
from app.models.order import Order
from app.schemas.menu import Money


class ReturnIn(BaseModel):
    """Body of ``POST /orders/{id}/return``: reason trimmed, then 5-1000 characters."""

    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]


class OwnerReturnOut(BaseModel):
    """One return request row for the owner dashboard (Req 20)."""

    id: int
    order_id: int
    status: OrderStatus
    payment_status: PaymentStatus
    return_status: ReturnStatus
    reason: str | None = None
    total_amount: Money
    requested_at: datetime | None = None
    return_requested_at: datetime | None = None
    customer_name: str
    restaurant_name: str

    @classmethod
    def from_order(cls, order: Order) -> "OwnerReturnOut":
        return cls(
            id=order.id,
            order_id=order.id,
            status=order.status,
            payment_status=order.payment_status,
            return_status=order.return_status,
            reason=order.return_reason,
            total_amount=order.total_amount,
            requested_at=order.return_requested_at,
            return_requested_at=order.return_requested_at,
            customer_name=order.customer.name,
            restaurant_name=order.restaurant.name,
        )


class ReturnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: int
    return_status: ReturnStatus
    reason: str | None = None
    requested_at: datetime | None = None
