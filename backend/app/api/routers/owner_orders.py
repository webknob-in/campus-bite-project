"""Restaurant owner order endpoints (Req 17, 18, 40.5, 40.6).

The owner's Restaurant is scoped inside every query, so another restaurant's Order is a 404.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_owner_restaurant, get_restaurant_order, require_roles
from app.core.errors import BadRequestError, InvalidTransitionError, NotFoundError
from app.models import Order, Restaurant, Role, User
from app.models.enums import OrderStatus
from app.schemas.common import Page, PageParams
from app.schemas.owner_order import (
    AssignPartnerIn,
    DeliveryPartnerOut,
    OwnerOrderOut,
    OwnerStatusUpdate,
)
from app.services.filters import OrderFilterParams
from app.services.order_state import Actor, transition
from app.services.pagination import paginate

router = APIRouter(prefix="/owner", tags=["owner-orders"])

_INT32_MAX = 2**31 - 1
_OWNER_TARGETS = {OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY}
_AUTH_RESPONSES = {
    401: {"description": "Missing or invalid token."},
    403: {"description": "Not a RESTAURANT_OWNER."},
}
_LOADERS = (
    selectinload(Order.items),
    selectinload(Order.customer),
    selectinload(Order.delivery_partner),
)


def _valid_id(value: int) -> bool:
    return 0 < value <= _INT32_MAX


def _load_order(db: Session, order_id: int, restaurant: Restaurant) -> Order:
    """Lock and return the owner's Order (404 otherwise) with display relations loaded."""
    if not _valid_id(order_id):
        raise NotFoundError("Order not found")
    order = get_restaurant_order(db, order_id, restaurant.id, for_update=True)
    db.refresh(order, attribute_names=["items", "customer", "delivery_partner"])
    return order


@router.get(
    "/orders",
    response_model=Page[OwnerOrderOut],
    summary="List my restaurant's orders, newest first",
    responses={**_AUTH_RESPONSES, 422: {"description": "Invalid filter or paging parameter."}},
)
def list_orders(
    filters: OrderFilterParams = Depends(),
    params: PageParams = Depends(),
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> Page[OwnerOrderOut]:
    stmt = (
        filters.apply(select(Order).where(Order.restaurant_id == restaurant.id))
        .options(*_LOADERS)
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    page = paginate(db, stmt, params)
    page["items"] = [OwnerOrderOut.from_order(o) for o in page["items"]]
    return Page[OwnerOrderOut](**page)


@router.patch(
    "/orders/{order_id}/status",
    response_model=OwnerOrderOut,
    summary="Move an order to ACCEPTED, PREPARING or READY",
    responses={
        **_AUTH_RESPONSES,
        404: {"description": "Order not found (or not in my restaurant)."},
        409: {"description": "Transition not allowed."},
        422: {"description": "Invalid status value."},
    },
)
def update_status(
    order_id: int,
    body: OwnerStatusUpdate,
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> OwnerOrderOut:
    order = _load_order(db, order_id, restaurant)
    if body.status not in _OWNER_TARGETS:
        raise InvalidTransitionError(
            f"Cannot change order from {order.status.value} to {body.status.value}"
        )
    transition(db, order, body.status, Actor.RESTAURANT_OWNER)
    db.flush()
    return OwnerOrderOut.from_order(order)


@router.get(
    "/delivery-partners",
    response_model=Page[DeliveryPartnerOut],
    summary="List delivery partners available for assignment",
    responses={**_AUTH_RESPONSES, 422: {"description": "Invalid paging parameter."}},
)
def list_delivery_partners(
    params: PageParams = Depends(),
    _owner: User = Depends(require_roles(Role.RESTAURANT_OWNER)),
    db: Session = Depends(get_db),
) -> Page[DeliveryPartnerOut]:
    stmt = (
        select(User)
        .where(User.role == Role.DELIVERY_PARTNER)
        .order_by(User.name, User.id)
    )
    page = paginate(db, stmt, params)
    page["items"] = [DeliveryPartnerOut(id=u.id, name=u.name, phone=u.phone) for u in page["items"]]
    return Page[DeliveryPartnerOut](**page)


@router.post(
    "/orders/{order_id}/assign",
    response_model=OwnerOrderOut,
    summary="Assign a delivery partner to a READY order",
    responses={
        **_AUTH_RESPONSES,
        400: {"description": "The user is not a delivery partner."},
        404: {"description": "Order not found (or not in my restaurant)."},
        409: {"description": "The order is not READY."},
    },
)
def assign_partner(
    order_id: int,
    body: AssignPartnerIn,
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> OwnerOrderOut:
    order = _load_order(db, order_id, restaurant)
    partner = db.get(User, body.delivery_partner_id) if _valid_id(body.delivery_partner_id) else None
    if partner is None or partner.role != Role.DELIVERY_PARTNER:
        raise BadRequestError("The selected user is not a delivery partner")
    transition(db, order, OrderStatus.ASSIGNED, Actor.RESTAURANT_OWNER)
    order.delivery_partner_id = partner.id
    db.flush()
    db.refresh(order, attribute_names=["delivery_partner"])
    return OwnerOrderOut.from_order(order)
