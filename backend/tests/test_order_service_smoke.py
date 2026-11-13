"""DB-backed smoke test of the order services called directly (task 6.3)."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.errors import BadRequestError, InvalidTransitionError, NotFoundError
from app.models import LedgerType, Order, OrderItem, OrderStatus, PaymentLedger, PaymentStatus, ReturnStatus
from app.schemas.common import PageParams
from app.schemas.order import OrderCreate, OrderDetailOut, OrderOut
from app.services.filters import OrderFilterParams, apply_order_filters
from app.services.order_service import (
    cancel_order,
    get_order_detail,
    list_customer_orders,
    place_order,
)
from tests.factories import make_customer, make_menu_item, make_order, make_restaurant

CARD = "4111111111111111"
CVV = "737"


def _payload(*lines, **overrides) -> OrderCreate:
    data = {
        "items": [{"menu_item_id": i, "quantity": q} for i, q in lines],
        "delivery_address": "Hostel 3, Room 12",
        "delivery_phone": "+91 98765 43210",
        "payment": {"card_holder": "Asha Rao", "card_number": CARD, "expiry": "12/99", "cvv": CVV},
    }
    data.update(overrides)
    return OrderCreate(**data)


def _counts(db) -> tuple[int, int, int]:
    return tuple(
        db.scalar(select(func.count()).select_from(model)) for model in (Order, OrderItem, PaymentLedger)
    )


def test_place_order_happy_path(db):
    customer = make_customer(db)
    restaurant = make_restaurant(db)
    a = make_menu_item(db, restaurant, price="12.34")
    b = make_menu_item(db, restaurant, price="0.10")

    order = place_order(db, customer, _payload((a.id, 3), (b.id, 7)))

    assert order.id is not None
    assert order.status is OrderStatus.PLACED
    assert order.payment_status is PaymentStatus.mock_paid
    assert order.return_status is ReturnStatus.none
    assert order.customer_id == customer.id and order.restaurant_id == restaurant.id
    assert order.total_amount == Decimal("37.02") + Decimal("0.70")
    assert sum(i.line_total for i in order.items) == order.total_amount
    assert {(i.name, i.unit_price, i.quantity) for i in order.items} == {
        (a.name, Decimal("12.34"), 3),
        (b.name, Decimal("0.10"), 7),
    }
    (ledger,) = order.ledger_entries
    assert ledger.entry_type is LedgerType.PAYMENT
    assert ledger.amount == order.total_amount
    assert ledger.status == "success"
    assert ledger.transaction_ref.startswith("MOCK-")
    assert ledger.card_last4 == CARD[-4:]

    # The card number and CVV appear nowhere in the stored rows or in the response.
    stored = db.scalar(select(PaymentLedger).where(PaymentLedger.order_id == order.id))
    persisted = [stored.transaction_ref, stored.card_last4, stored.status, order.delivery_address]
    assert not any(CARD in str(v) or CVV in str(v) for v in persisted)
    detail = OrderDetailOut.from_order(get_order_detail(db, customer, order.id))
    dumped = detail.model_dump_json()
    assert CARD not in dumped and "cvv" not in dumped
    assert detail.total_amount == Decimal("37.72")
    assert '"total_amount":"37.72"' in dumped
    assert detail.restaurant_name == restaurant.name
    assert detail.review is None and detail.delivery_partner_name is None
    assert len(detail.ledger_entries) == 1


def test_duplicate_item_ids_are_merged(db):
    customer = make_customer(db)
    item = make_menu_item(db, price="5.00")

    order = place_order(db, customer, _payload((item.id, 2), (item.id, 3)))

    assert len(order.items) == 1
    assert order.items[0].quantity == 5
    assert order.total_amount == Decimal("25.00")


def test_client_cannot_change_prices(db):
    customer = make_customer(db)
    item = make_menu_item(db, price="5.00")
    payload = OrderCreate.model_validate(
        {
            "items": [{"menu_item_id": item.id, "quantity": 1, "unit_price": "0.01"}],
            "delivery_address": "Hostel 3, Room 12",
            "delivery_phone": "9876543210",
            "payment": {"card_holder": "Asha Rao", "card_number": CARD, "expiry": "12/99", "cvv": CVV},
            "total_amount": "0.01",
        }
    )
    assert place_order(db, customer, payload).total_amount == Decimal("5.00")


def _assert_rejected(db, customer, payload, exc=BadRequestError):
    before = _counts(db)
    with pytest.raises(exc):
        place_order(db, customer, payload)
    assert _counts(db) == before


def test_unavailable_missing_closed_multi_restaurant_leave_no_rows(db):
    customer = make_customer(db)
    restaurant = make_restaurant(db)
    good = make_menu_item(db, restaurant)
    unavailable = make_menu_item(db, restaurant, is_available=False)
    other = make_menu_item(db)
    closed_item = make_menu_item(db, make_restaurant(db, is_open=False))

    _assert_rejected(db, customer, _payload((good.id, 1), (unavailable.id, 1)))
    with pytest.raises(BadRequestError, match=str(unavailable.id)):
        place_order(db, customer, _payload((unavailable.id, 1)))
    _assert_rejected(db, customer, _payload((good.id, 1), (999_999, 1)))
    _assert_rejected(db, customer, _payload((good.id, 1), (2**40, 1)))
    _assert_rejected(db, customer, _payload((good.id, 1), (other.id, 1)))
    _assert_rejected(db, customer, _payload((closed_item.id, 1)))
    # 60 + 60 of the same dish is a merged quantity above 99 -> 422
    _assert_rejected(db, customer, _payload((good.id, 60), (good.id, 60)), RequestValidationError)


@pytest.mark.parametrize(
    "bad",
    [
        {"items": []},
        {"items": [{"menu_item_id": 1, "quantity": 0}]},
        {"items": [{"menu_item_id": 1, "quantity": 100}]},
        {"items": [{"menu_item_id": 1, "quantity": True}]},
        {"items": [{"menu_item_id": 1, "quantity": "2"}]},
        {"delivery_address": "abc"},
        {"delivery_phone": "12ab567"},
        {"payment": {"card_holder": "A B", "card_number": "123456789012345", "expiry": "12/99", "cvv": CVV}},
        {"payment": {"card_holder": "A B", "card_number": CARD, "expiry": "13/99", "cvv": CVV}},
        {"payment": {"card_holder": "A B", "card_number": CARD, "expiry": "01/20", "cvv": CVV}},
        {"payment": {"card_holder": "A B", "card_number": CARD, "expiry": "12/99", "cvv": "12"}},
    ],
)
def test_invalid_payload_is_rejected(bad):
    valid = {
        "items": [{"menu_item_id": 1, "quantity": 1}],
        "delivery_address": "Hostel 3, Room 12",
        "delivery_phone": "9876543210",
        "payment": {"card_holder": "A B", "card_number": CARD, "expiry": "12/99", "cvv": CVV},
    }
    with pytest.raises(ValidationError):
        OrderCreate(**{**valid, **bad})


def test_current_month_expiry_is_accepted():
    now = datetime.now(timezone.utc)
    expiry = f"{now.month:02d}/{now.year % 100:02d}"
    OrderCreate(
        items=[{"menu_item_id": 1, "quantity": 1}],
        delivery_address="Hostel 3, Room 12",
        delivery_phone="9876543210",
        payment={"card_holder": "A B", "card_number": CARD, "expiry": expiry, "cvv": CVV},
    )


def test_card_details_are_not_in_repr():
    payload = _payload((1, 1))
    assert CARD not in repr(payload) and CVV not in repr(payload)


def test_cancel_placed_then_accepted_conflicts(db):
    customer = make_customer(db)
    item = make_menu_item(db)
    placed = place_order(db, customer, _payload((item.id, 1)))

    cancelled = cancel_order(db, customer, placed.id)
    assert cancelled.status is OrderStatus.CANCELLED
    with pytest.raises(InvalidTransitionError):
        cancel_order(db, customer, placed.id)

    accepted = make_order(db, OrderStatus.ACCEPTED, customer=customer)
    with pytest.raises(InvalidTransitionError):
        cancel_order(db, customer, accepted.id)
    db.refresh(accepted)
    assert accepted.status is OrderStatus.ACCEPTED

    delivered = make_order(db, OrderStatus.DELIVERED, customer=customer)
    with pytest.raises(InvalidTransitionError):
        cancel_order(db, customer, delivered.id)


def test_other_customers_orders_are_not_found(db):
    owner_customer, other = make_customer(db), make_customer(db)
    order = make_order(db, customer=owner_customer)
    with pytest.raises(NotFoundError):
        get_order_detail(db, other, order.id)
    with pytest.raises(NotFoundError):
        cancel_order(db, other, order.id)
    with pytest.raises(NotFoundError):
        get_order_detail(db, owner_customer, 2**40)
    with pytest.raises(NotFoundError):
        cancel_order(db, owner_customer, 2**40)
    db.refresh(order)
    assert order.status is OrderStatus.PLACED


def test_list_orders_scoped_ordered_filtered_and_paged(db):
    me, other = make_customer(db), make_customer(db)
    now = datetime.now(timezone.utc)
    old = make_order(db, customer=me, created_at=now - timedelta(days=10))
    mid = make_order(db, OrderStatus.DELIVERED, customer=me, created_at=now - timedelta(days=5))
    new = make_order(db, customer=me, created_at=now - timedelta(days=1))
    make_order(db, customer=other)

    page = list_customer_orders(db, me, OrderFilterParams(), PageParams())
    assert [o.id for o in page.items] == [new.id, mid.id, old.id]
    assert page.total == 3
    assert isinstance(page.items[0], OrderOut) and page.items[0].items

    only = list_customer_orders(db, me, OrderFilterParams(status=OrderStatus.DELIVERED), PageParams())
    assert [o.id for o in only.items] == [mid.id]

    paged = list_customer_orders(db, me, OrderFilterParams(), PageParams(page=2, page_size=2))
    assert [o.id for o in paged.items] == [old.id] and paged.total == 3

    day = (now - timedelta(days=5)).date()
    on_day = list_customer_orders(db, me, OrderFilterParams(date_from=day, date_to=day), PageParams())
    assert [o.id for o in on_day.items] == [mid.id]
    since = list_customer_orders(db, me, OrderFilterParams(date_from=day), PageParams())
    assert [o.id for o in since.items] == [new.id, mid.id]
    until = list_customer_orders(db, me, OrderFilterParams(date_to=day), PageParams())
    assert [o.id for o in until.items] == [mid.id, old.id]


def test_date_filter_uses_inclusive_utc_day_bounds(db):
    me = make_customer(db)
    day = date(2024, 3, 10)
    start = datetime(2024, 3, 10, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 3, 10, 23, 59, 59, tzinfo=timezone.utc)
    before = make_order(db, customer=me, created_at=start - timedelta(seconds=1))
    first = make_order(db, customer=me, created_at=start)
    last = make_order(db, customer=me, created_at=end)
    after = make_order(db, customer=me, created_at=end + timedelta(seconds=1))

    stmt = apply_order_filters(select(Order.id).where(Order.customer_id == me.id), None, day, day)
    assert set(db.scalars(stmt)) == {first.id, last.id}
    assert before.id not in set(db.scalars(stmt)) and after.id not in set(db.scalars(stmt))
    # date.max has no "next day"; it simply means no upper bound.
    assert apply_order_filters(select(Order.id), None, None, date.max) is not None


def test_date_from_after_date_to_is_422():
    with pytest.raises(RequestValidationError):
        apply_order_filters(select(Order), None, date(2024, 3, 11), date(2024, 3, 10))
    with pytest.raises(RequestValidationError):
        OrderFilterParams(date_from=date(2024, 3, 11), date_to=date(2024, 3, 10))
