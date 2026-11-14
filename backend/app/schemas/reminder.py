from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import OrderStatus


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    restaurant_id: int
    status_at_reminder: OrderStatus
    message: str
    is_resolved: bool
    created_at: datetime
