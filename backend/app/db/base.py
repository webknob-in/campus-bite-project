from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime (all timestamps are UTC)."""
    return datetime.now(timezone.utc)
