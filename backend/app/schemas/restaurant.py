"""Public restaurant response schema (Req 8.1, 8.3)."""
from pydantic import BaseModel, ConfigDict


class RestaurantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    cuisine: str
    address: str
    image_url: str | None = None
    is_open: bool
    # Mean of the restaurant's review ratings rounded to 2 places; null when it has no reviews.
    average_rating: float | None = None
    review_count: int = 0
