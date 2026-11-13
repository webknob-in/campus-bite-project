"""Delivery partner endpoints (Req 21, 40.5).

Every query is scoped to ``delivery_partner_id == caller``, so another partner's Order is a 404.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_partner_order, require_roles
from app.core.errors import InvalidTransitionError, NotFoundError
from app.models import Order, Role, User
from app.models.enums import OrderStatus
from app.schemas.common import Page, PageParams
from app.schemas.partner import PartnerOrderOut, PartnerStatusUpdate
from app.services.order_state import Actor, transition
from app.services.pagination import paginate

router = APIRouter(prefix="/partner", tags=["partner"])

_INT32_MAX = 2**31 - 1
_PARTNER_TARGETS = {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED}
_ACTIVE = (OrderStatus.ASSIGNED, OrderStatus.OUT_FOR_DELIVERY)
_HISTORY = (OrderStatus.DELIVERED, OrderStatus.REFUNDED)
_AUTH_RESPONSES = {
    401: {"description": "Missing or invalid token."},
    403: {"description": "Not a DELIVERY_PARTNER."},
}
_LOADERS = (
    selectinload(Order.items),
    selectinload(Order.customer),
    selectinload(Order.restaurant),
)
_partner_only = require_roles(Role.DELIVERY_PARTNER)


def _check_id(order_id: int) -> None:
    if not 0 < order_id <= _INT32_MAX:
        raise NotFoundError("Order not found")


@router.get(
    "/orders",
    response_model=Page[PartnerOrderOut],
    summary="List my assigned orders (active by default), newest first",
    responses={**_AUTH_RESPONSES, 422: {"description": "Invalid filter or paging parameter."}},
)
def list_orders(
    status: OrderStatus | None = None,
    params: PageParams = Depends(),
    partner: User = Depends(_partner_only),
    db: Session = Depends(get_db),
) -> Page[PartnerOrderOut]:
    stmt = select(Order).where(Order.delivery_partner_id == partner.id)
    stmt = stmt.where(Order.status == status) if status else stmt.where(Order.status.in_(_ACTIVE))
    stmt = stmt.options(*_LOADERS).order_by(Order.created_at.desc(), Order.id.desc())
    page = paginate(db, stmt, params)
    page["items"] = [PartnerOrderOut.from_order(o) for o in page["items"]]
    return Page[PartnerOrderOut](**page)


@router.get(
    "/history",
    response_model=Page[PartnerOrderOut],
    summary="My delivered and refunded orders, newest delivery first",
    responses={**_AUTH_RESPONSES, 422: {"description": "Invalid paging parameter."}},
)
def history(
    params: PageParams = Depends(),
    partner: User = Depends(_partner_only),
    db: Session = Depends(get_db),
) -> Page[PartnerOrderOut]:
    stmt = (
        select(Order)
        .where(Order.delivery_partner_id == partner.id, Order.status.in_(_HISTORY))
        .options(*_LOADERS)
        .order_by(Order.delivered_at.desc().nulls_last(), Order.id.desc())
    )
    page = paginate(db, stmt, params)
    page["items"] = [PartnerOrderOut.from_order(o) for o in page["items"]]
    return Page[PartnerOrderOut](**page)


@router.get(
    "/orders/{order_id}",
    response_model=PartnerOrderOut,
    summary="Get one of my assigned orders",
    responses={**_AUTH_RESPONSES, 404: {"description": "Order not found (or not assigned to me)."}},
)
def get_order(
    order_id: int,
    partner: User = Depends(_partner_only),
    db: Session = Depends(get_db),
) -> PartnerOrderOut:
    _check_id(order_id)
    order = get_partner_order(db, order_id, partner.id)
    db.refresh(order, attribute_names=["items", "customer", "restaurant"])
    return PartnerOrderOut.from_order(order)


@router.patch(
    "/orders/{order_id}/status",
    response_model=PartnerOrderOut,
    summary="Move my order to OUT_FOR_DELIVERY or DELIVERED",
    responses={
        **_AUTH_RESPONSES,
        404: {"description": "Order not found (or not assigned to me)."},
        409: {"description": "Transition not allowed."},
        422: {"description": "Invalid status value."},
    },
)
def update_status(
    order_id: int,
    body: PartnerStatusUpdate,
    partner: User = Depends(_partner_only),
    db: Session = Depends(get_db),
) -> PartnerOrderOut:
    _check_id(order_id)
    order = get_partner_order(db, order_id, partner.id, for_update=True)
    if body.status not in _PARTNER_TARGETS:
        raise InvalidTransitionError(
            f"Cannot change order from {order.status.value} to {body.status.value}"
        )
    transition(db, order, body.status, Actor.ASSIGNED_PARTNER)
    db.flush()
    db.refresh(order, attribute_names=["items", "customer", "restaurant"])
    return PartnerOrderOut.from_order(order)
