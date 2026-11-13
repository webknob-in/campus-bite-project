"""Review schemas (Req 14)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class ReviewIn(BaseModel):
    """Body of ``POST /orders/{id}/review``: strict integer rating 1-5, optional comment <= 1000."""

    rating: StrictInt = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment", mode="after")
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ReviewCreatedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    restaurant_id: int
    customer_id: int
    rating: int
    comment: str | None = None
    created_at: datetime
