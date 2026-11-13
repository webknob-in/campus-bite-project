"""Restaurant owner return/refund decisions (Req 20, 23.2, 40.8)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_owner_restaurant
from app.models import Order, Restaurant
from app.models.enums import ReturnStatus
from app.schemas.common import Page, PageParams
from app.schemas.returns import OwnerReturnOut
from app.services import return_service
from app.services.pagination import paginate

router = APIRouter(prefix="/owner/returns", tags=["owner-returns"])

_RESPONSES = {
    401: {"description": "Missing or invalid token."},
    403: {"description": "Not a RESTAURANT_OWNER."},
}
_DECISION_RESPONSES = {
    **_RESPONSES,
    404: {"description": "Order not found (or not in my restaurant)."},
    409: {"description": "The return is not in the requested state."},
}


def _reload(db: Session, order: Order) -> OwnerReturnOut:
    db.refresh(order, attribute_names=["customer", "restaurant"])
    return OwnerReturnOut.from_order(order)


@router.get(
    "",
    response_model=Page[OwnerReturnOut],
    summary="List my restaurant's return requests",
    responses={**_RESPONSES, 422: {"description": "Invalid filter or paging parameter."}},
)
def list_returns(
    status: ReturnStatus | None = Query(default=None, description="Filter by return status"),
    params: PageParams = Depends(),
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> Page[OwnerReturnOut]:
    stmt = select(Order).where(Order.restaurant_id == restaurant.id)
    if status is None:
        stmt = stmt.where(Order.return_status != ReturnStatus.none)
    else:
        stmt = stmt.where(Order.return_status == status)
    stmt = stmt.options(selectinload(Order.customer), selectinload(Order.restaurant)).order_by(
        Order.return_requested_at.desc(), Order.id.desc()
    )
    page = paginate(db, stmt, params)
    page["items"] = [OwnerReturnOut.from_order(o) for o in page["items"]]
    return Page[OwnerReturnOut](**page)


@router.post(
    "/{order_id}/approve",
    response_model=OwnerReturnOut,
    summary="Approve a return and refund the order",
    responses=_DECISION_RESPONSES,
)
def approve(
    order_id: int,
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> OwnerReturnOut:
    return _reload(db, return_service.approve_return(db, restaurant.id, order_id))


@router.post(
    "/{order_id}/reject",
    response_model=OwnerReturnOut,
    summary="Reject a return request",
    responses=_DECISION_RESPONSES,
)
def reject(
    order_id: int,
    restaurant: Restaurant = Depends(get_owner_restaurant),
    db: Session = Depends(get_db),
) -> OwnerReturnOut:
    return _reload(db, return_service.reject_return(db, restaurant.id, order_id))
