"""Customer order endpoints (Req 11, 12, 13, 40.3-40.5).

Every route requires the CUSTOMER role. An Order of another customer is a 404, never a 403.
Declare ``GET /orders/me`` before ``GET /orders/{order_id}`` so ``me`` is not parsed as an id.
Review and return routes (``/orders/{order_id}/review`` and ``/return``) are added to this router.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models import Role, User
from app.schemas.common import Page, PageParams
from app.schemas.order import OrderCreate, OrderDetailOut, OrderOut
from app.schemas.review import ReviewCreatedOut, ReviewIn
from app.schemas.returns import ReturnIn
from app.services import order_service, return_service, review_service
from app.services.filters import OrderFilterParams

router = APIRouter(prefix="/orders", tags=["orders"])

_AUTH_RESPONSES = {
    401: {"description": "Missing or invalid token."},
    403: {"description": "Not a CUSTOMER."},
}
_ORDER_RESPONSES = {**_AUTH_RESPONSES, 404: {"description": "Order not found (or not the caller's)."}}


@router.post(
    "",
    response_model=OrderDetailOut,
    status_code=201,
    summary="Place an order with a dummy card payment",
    responses={
        **_AUTH_RESPONSES,
        400: {"description": "Item unavailable, restaurant closed, or items from several restaurants."},
        422: {"description": "Invalid request body."},
    },
)
def place_order(
    body: OrderCreate,
    customer: User = Depends(require_roles(Role.CUSTOMER)),
    db: Session = Depends(get_db),
) -> OrderDetailOut:
    order = order_service.place_order(db, customer, body)
    return OrderDetailOut.from_order(order)


@router.get(
    "/me",
    response_model=Page[OrderOut],
    summary="List my orders, newest first",
    responses={**_AUTH_RESPONSES, 422: {"description": "Invalid filter or paging parameter."}},
)
def list_my_orders(
    filters: OrderFilterParams = Depends(),
    params: PageParams = Depends(),
    customer: User = Depends(require_roles(Role.CUSTOMER)),
    db: Session = Depends(get_db),
) -> Page[OrderOut]:
    return order_service.list_customer_orders(db, customer, filters, params)


@router.get(
    "/{order_id}",
    response_model=OrderDetailOut,
    summary="Get one of my orders",
    responses=_ORDER_RESPONSES,
)
def get_order(
    order_id: int,
    customer: User = Depends(require_roles(Role.CUSTOMER)),
    db: Session = Depends(get_db),
) -> OrderDetailOut:
    return OrderDetailOut.from_order(order_service.get_order_detail(db, customer, order_id))


@router.post(
    "/{order_id}/review",
    response_model=ReviewCreatedOut,
    status_code=201,
    summary="Review a delivered or refunded order",
    responses={
        **_ORDER_RESPONSES,
        409: {"description": "Order not DELIVERED/REFUNDED, or already reviewed."},
        422: {"description": "Invalid rating or comment."},
    },
)
def review_order(
    order_id: int,
    body: ReviewIn,
    customer: User = Depends(require_roles(Role.CUSTOMER)),
    db: Session = Depends(get_db),
) -> ReviewCreatedOut:
    review = review_service.create_review(db, customer, order_id, body)
    return ReviewCreatedOut.model_validate(review)


@router.post(
    "/{order_id}/return",
    response_model=OrderDetailOut,
    summary="Request a return for a delivered order",
    responses={
        **_ORDER_RESPONSES,
        409: {"description": "Order not DELIVERED, or a return was already requested."},
        422: {"description": "Reason missing, blank, or not 5-1000 characters."},
    },
)
def request_order_return(
    order_id: int,
    body: ReturnIn,
    customer: User = Depends(require_roles(Role.CUSTOMER)),
    db: Session = Depends(get_db),
) -> OrderDetailOut:
    return_service.request_return(db, customer, order_id, body)
    return OrderDetailOut.from_order(order_service.get_order_detail(db, customer, order_id))


@router.post(
    "/{order_id}/cancel",
    response_model=OrderDetailOut,
    summary="Cancel one of my orders while it is still PLACED",
    responses={**_ORDER_RESPONSES, 409: {"description": "The order is no longer PLACED."}},
)
def cancel_order(
    order_id: int,
    customer: User = Depends(require_roles(Role.CUSTOMER)),
    db: Session = Depends(get_db),
) -> OrderDetailOut:
    order_service.cancel_order(db, customer, order_id)
    # Reload with the detail loaders so the response is built from the stored row.
    return OrderDetailOut.from_order(order_service.get_order_detail(db, customer, order_id))
