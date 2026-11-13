"""Return request schemas (Req 15)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models.enums import ReturnStatus


class ReturnIn(BaseModel):
    """Body of ``POST /orders/{id}/return``: reason trimmed, then 5-1000 characters."""

    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]


class ReturnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: int
    return_status: ReturnStatus
    reason: str | None = None
    requested_at: datetime | None = None
