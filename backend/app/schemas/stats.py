"""Restaurant statistics response schema (Req 19.1-19.3)."""

from pydantic import BaseModel

from app.schemas.menu import Money


class TopDishOut(BaseModel):
    name: str
    quantity: int


class StatsOut(BaseModel):
    total_orders: int
    orders_today: int
    net_revenue: Money
    average_rating: float | None
    status_counts: dict[str, int]
    top_dishes: list[TopDishOut]
