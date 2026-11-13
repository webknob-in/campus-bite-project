"""FastAPI dependencies: DB session, authentication, role checks and tenant-scoped lookups.

Authentication failures raise ``UnauthorizedError`` (401 with ``WWW-Authenticate: Bearer``),
a wrong Role raises ``ForbiddenError`` (403) and a record outside the caller's tenant raises
``NotFoundError`` (404), so a foreign object looks exactly like a missing one (Req 6.1-6.5).
"""

from collections.abc import Callable, Iterator

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models import Order, Restaurant, Role, User

# ``auto_error=False`` so a missing header yields our 401 (with the same body and header as an
# invalid token) instead of FastAPI's default 403.
bearer = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    """Yield one Session per request inside a single transaction.

    Commits when the request handler finishes without raising, and rolls back on any
    exception so a failed request never leaves partial writes (Req 47.4). Services that
    must turn a constraint violation into a 409 should ``flush()`` inside their own
    ``try``/``except IntegrityError`` so the error surfaces before this commit.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Return the User identified by the Bearer JWT, or raise 401.

    The Role used for authorization is the one stored in the database, not the ``role`` claim,
    so a role change takes effect immediately.
    """
    if creds is None:
        raise UnauthorizedError("Not authenticated")
    try:
        payload = decode_access_token(creds.credentials, get_settings())
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise UnauthorizedError("Invalid or expired token") from None
    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("Invalid or expired token")
    return user


def require_roles(*roles: Role) -> Callable[..., User]:
    """Build a dependency that returns the current User if their Role is in ``roles``, else 403."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError("You do not have permission for this action")
        return user

    return checker


def get_owner_restaurant(
    user: User = Depends(require_roles(Role.RESTAURANT_OWNER)),
    db: Session = Depends(get_db),
) -> Restaurant:
    """Return the Restaurant owned by the current RESTAURANT_OWNER, or 404 if they have none."""
    restaurant = db.scalar(select(Restaurant).where(Restaurant.owner_id == user.id))
    if restaurant is None:
        raise NotFoundError("Restaurant not found")
    return restaurant


def _get_order(db: Session, order_id: int, tenant_predicate: object, for_update: bool) -> Order:
    stmt = select(Order).where(Order.id == order_id, tenant_predicate)  # type: ignore[arg-type]
    if for_update:
        # Concurrent transitions on the same Order serialize on this row lock.
        stmt = stmt.with_for_update()
    order = db.scalar(stmt)
    if order is None:
        raise NotFoundError("Order not found")
    return order


def get_customer_order(db: Session, order_id: int, customer_id: int, *, for_update: bool = False) -> Order:
    """Return the Order if it belongs to ``customer_id``, else 404 (``WHERE customer_id = :cid``)."""
    return _get_order(db, order_id, Order.customer_id == customer_id, for_update)


def get_restaurant_order(db: Session, order_id: int, restaurant_id: int, *, for_update: bool = False) -> Order:
    """Return the Order if it belongs to ``restaurant_id``, else 404 (``WHERE restaurant_id = :rid``)."""
    return _get_order(db, order_id, Order.restaurant_id == restaurant_id, for_update)


def get_partner_order(db: Session, order_id: int, partner_id: int, *, for_update: bool = False) -> Order:
    """Return the Order if it is assigned to ``partner_id``, else 404 (``WHERE delivery_partner_id = :pid``)."""
    return _get_order(db, order_id, Order.delivery_partner_id == partner_id, for_update)
