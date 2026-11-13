"""Customer order services: place with dummy payment, list, detail and cancel (Req 11-13, 23, 24, 47)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from fastapi.exceptions import RequestValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import get_customer_order
from app.core.errors import BadRequestError, NotFoundError
from app.db.base import utcnow
from app.models import (
    LedgerType,
    MenuItem,
    Order,
    OrderItem,
    OrderStatus,
    PaymentLedger,
    PaymentStatus,
    Restaurant,
    ReturnStatus,
    User,
)
from app.schemas.common import Page, PageParams
from app.schemas.order import OrderCreate, OrderOut
from app.services.filters import OrderFilterParams
from app.services.order_state import Actor, transition
from app.services.pagination import paginate

_CENT = Decimal("0.01")
_MAX_QUANTITY = 99
_INT32_MAX = 2**31 - 1  # ids are PostgreSQL INTEGER; larger values cannot exist
_MAX_TOTAL = Decimal("99999999.99")  # Numeric(10, 2)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _valid_id(value: int) -> bool:
    return 0 < value <= _INT32_MAX


def _merge_items(payload: OrderCreate) -> dict[int, int]:
    """Merge lines with the same ``menu_item_id`` (keeping first-seen order) and sum quantities."""
    merged: dict[int, int] = {}
    for line in payload.items:
        merged[line.menu_item_id] = merged.get(line.menu_item_id, 0) + line.quantity
    for menu_item_id, quantity in merged.items():
        if quantity > _MAX_QUANTITY:
            raise RequestValidationError(
                [
                    {
                        "type": "value_error",
                        "loc": ("body", "items"),
                        "msg": f"Total quantity for menu item {menu_item_id} must not exceed {_MAX_QUANTITY}",
                        "input": menu_item_id,
                    }
                ]
            )
    return merged


def _order_loader_options() -> list:
    return [
        selectinload(Order.items),
        selectinload(Order.ledger_entries),
        joinedload(Order.restaurant),
        joinedload(Order.review),
        joinedload(Order.delivery_partner),
    ]


def place_order(db: Session, customer: User, payload: OrderCreate) -> Order:
    """Create a ``PLACED`` Order with its lines and a ``PAYMENT`` ledger entry (Req 11, 23.1, 47).

    Everything is validated before the first row is added, so a rejected request (400/422)
    leaves no trace. Prices come from the database, never from the client. The card number
    and CVV are not read after validation; only the last 4 digits are stored. Does not commit.
    """
    merged = _merge_items(payload)

    ids = [i for i in merged if _valid_id(i)]
    found: dict[int, MenuItem] = {}
    if ids:
        found = {m.id: m for m in db.scalars(select(MenuItem).where(MenuItem.id.in_(ids)))}
    for menu_item_id in merged:
        menu_item = found.get(menu_item_id)
        if menu_item is None or not menu_item.is_available:
            raise BadRequestError(f"Menu item {menu_item_id} is not available")

    restaurant_ids = {m.restaurant_id for m in found.values()}
    if len(restaurant_ids) != 1:
        raise BadRequestError("All items must come from one restaurant")
    restaurant = db.get(Restaurant, restaurant_ids.pop())
    if restaurant is None or not restaurant.is_open:
        raise BadRequestError("Restaurant is closed")

    lines: list[OrderItem] = []
    total = Decimal("0.00")
    for menu_item_id, quantity in merged.items():
        menu_item = found[menu_item_id]
        unit_price = _quantize(menu_item.price)
        line_total = _quantize(unit_price * quantity)
        total += line_total
        lines.append(
            OrderItem(
                menu_item_id=menu_item.id,
                name=menu_item.name,
                unit_price=unit_price,
                quantity=quantity,
                line_total=line_total,
            )
        )
    total = _quantize(total)
    if total > _MAX_TOTAL:
        raise BadRequestError("Order total is too large")

    now = utcnow()
    order = Order(
        customer_id=customer.id,
        restaurant_id=restaurant.id,
        status=OrderStatus.PLACED,
        total_amount=total,
        delivery_address=payload.delivery_address,
        delivery_phone=payload.delivery_phone,
        payment_status=PaymentStatus.mock_paid,
        return_status=ReturnStatus.none,
        created_at=now,
        updated_at=now,
        status_updated_at=now,
    )
    order.restaurant = restaurant
    order.items = lines
    order.ledger_entries = [
        PaymentLedger(
            entry_type=LedgerType.PAYMENT,
            amount=total,
            status="success",
            transaction_ref="MOCK-" + uuid4().hex[:12].upper(),
            card_last4=payload.payment.card_number[-4:],
            created_at=now,
        )
    ]
    db.add(order)
    db.flush()
    return order


def list_customer_orders(
    db: Session, customer: User, filters: OrderFilterParams, params: PageParams
) -> Page[OrderOut]:
    """The customer's own Orders, newest first, filtered by status and created date (Req 12.1, 24.2, 24.3)."""
    stmt = (
        select(Order)
        .where(Order.customer_id == customer.id)
        .options(selectinload(Order.items), joinedload(Order.restaurant))
    )
    stmt = filters.apply(stmt).order_by(Order.created_at.desc(), Order.id.desc())
    page = paginate(db, stmt, params)
    page["items"] = [OrderOut.from_order(order) for order in page["items"]]
    return Page[OrderOut](**page)


def get_order_detail(db: Session, customer: User, order_id: int) -> Order:
    """The customer's own Order with items, ledger entries, review and partner loaded, else 404.

    Build the response with ``OrderDetailOut.from_order``.
    """
    order = None
    if _valid_id(order_id):
        order = db.scalar(
            select(Order)
            .where(Order.id == order_id, Order.customer_id == customer.id)
            .options(*_order_loader_options())
        )
    if order is None:
        raise NotFoundError("Order not found")
    return order


def cancel_order(db: Session, customer: User, order_id: int) -> Order:
    """Move the customer's own ``PLACED`` Order to ``CANCELLED``; 404 if not theirs, 409 if not PLACED."""
    if not _valid_id(order_id):
        raise NotFoundError("Order not found")
    order = get_customer_order(db, order_id, customer.id, for_update=True)
    transition(db, order, OrderStatus.CANCELLED, Actor.ORDER_CUSTOMER)
    db.flush()
    return order
