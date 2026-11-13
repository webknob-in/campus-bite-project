from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.menu_item import MenuItem
    from app.models.order import Order
    from app.models.review import Review
    from app.models.user import User


class Restaurant(Base):
    __tablename__ = "restaurants"
    # The unique constraint on owner_id also indexes the FK column.
    __table_args__ = (UniqueConstraint("owner_id", name="uq_restaurants_owner_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text)
    cuisine: Mapped[str] = mapped_column(String(60))
    address: Mapped[str] = mapped_column(String(300))
    image_url: Mapped[str | None] = mapped_column(String(500))
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User] = relationship(back_populates="restaurant")
    menu_items: Mapped[list[MenuItem]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan", passive_deletes=True
    )
    orders: Mapped[list[Order]] = relationship(back_populates="restaurant")
    reviews: Mapped[list[Review]] = relationship(back_populates="restaurant")
