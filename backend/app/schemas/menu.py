"""Menu item, dish and review response schemas (Req 8.5, 8.6, 9.6)."""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer

_CENT = Decimal("0.01")


def _serialize_money(value: Decimal) -> str:
    """Render a ``Decimal`` as a plain decimal string with exactly two places (``"12.50"``)."""
    return format(Decimal(value).quantize(_CENT, rounding=ROUND_HALF_UP), "f")


# Money stays an exact ``Decimal`` in Python and is sent as a JSON string such as "12.50",
# so no float rounding can ever change an amount on the wire.
Money = Annotated[
    Decimal,
    PlainSerializer(_serialize_money, return_type=str, when_used="json"),
]


class MenuItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restaurant_id: int
    name: str
    description: str | None = None
    price: Money
    category: str | None = None
    image_url: str | None = None
    is_available: bool


class DishOut(MenuItemOut):
    """A menu item from the cross-restaurant search, with its restaurant's name (Req 9.6)."""

    restaurant_name: str


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    restaurant_id: int
    rating: int
    comment: str | None = None
    customer_name: str
    created_at: datetime
