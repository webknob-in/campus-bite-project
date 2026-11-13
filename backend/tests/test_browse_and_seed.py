"""Unit tests for public browsing edge cases and the idempotent demo seed.

Covers Requirements 8.4 (unknown restaurant -> 404), 8.6 (reviews newest first), 9.6 (dish items
carry restaurant id and name) and 42.2 (running the seed twice creates nothing the second time).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import (
    LedgerType,
    MenuItem,
    Order,
    OrderStatus,
    PaymentLedger,
    Restaurant,
    Review,
    Role,
    User,
)
from scripts.seed import DEMO_PASSWORD, seed
from tests.factories import make_menu_item, make_order, make_restaurant, make_review

SEED_TABLES = (
    "users",
    "restaurants",
    "menu_items",
    "orders",
    "order_items",
    "payment_ledger",
    "reviews",
    "admin_reminder_logs",
)


# ------------------------------------------------------------------------------ browsing


@pytest.mark.parametrize("restaurant_id", [987654321, 2**31, 99999999999999])
@pytest.mark.parametrize("suffix", ["", "/menu", "/reviews"])
def test_unknown_restaurant_returns_404(client, restaurant_id, suffix):
    response = client.get(f"/restaurants/{restaurant_id}{suffix}")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_reviews_newest_first_with_id_desc_tie_break(client, db):
    restaurant = make_restaurant(db)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    def review(created_at):
        order = make_order(db, OrderStatus.DELIVERED, restaurant=restaurant)
        return make_review(db, order, created_at=created_at)

    oldest = review(now - timedelta(days=5))
    tie_a = review(now - timedelta(days=1))
    newest = review(now)
    tie_b = review(now - timedelta(days=1))
    middle = review(now - timedelta(days=2))
    # A review for another restaurant must not appear.
    make_review(db, make_order(db, OrderStatus.DELIVERED), created_at=now)

    body = client.get(f"/restaurants/{restaurant.id}/reviews").json()
    assert tie_b.id > tie_a.id
    assert [i["id"] for i in body["items"]] == [
        newest.id, tie_b.id, tie_a.id, middle.id, oldest.id,
    ]
    assert body["total"] == 5


def test_dish_items_include_restaurant_id_and_name(client, db):
    restaurant = make_restaurant(db, name="Dish Source Kitchen")
    dish = make_menu_item(db, restaurant, name="Unique Dish Qxv")

    items = client.get("/dishes", params={"search": "Qxv"}).json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == dish.id
    assert items[0]["restaurant_id"] == restaurant.id
    assert items[0]["restaurant_name"] == "Dish Source Kitchen"


# ----------------------------------------------------------------------------------- seed


def _table_counts(db):
    from app.db.base import Base

    return {
        name: db.scalar(select(func.count()).select_from(Base.metadata.tables[name]))
        for name in SEED_TABLES
    }


@pytest.fixture
def seeded(db):
    """Run the seed once on the per-test session and return its result."""
    return seed(db)


def test_seed_twice_keeps_row_counts_identical(db):
    first = seed(db)
    counts_after_first = _table_counts(db)
    assert counts_after_first["users"] == 7
    assert sum(first["created"].values()) > 0

    second = seed(db)
    counts_after_second = _table_counts(db)

    assert counts_after_second == counts_after_first
    assert second["created"]
    assert all(n == 0 for n in second["created"].values())
    assert second["credentials"] == first["credentials"]


def test_seed_creates_expected_users_restaurants_and_dishes(db, seeded):
    roles = [u.role for u in db.scalars(select(User))]
    assert roles.count(Role.RESTAURANT_OWNER) == 3
    assert roles.count(Role.DELIVERY_PARTNER) == 2
    assert roles.count(Role.CUSTOMER) == 2

    restaurants = list(db.scalars(select(Restaurant)))
    assert len(restaurants) == 3
    assert len({r.owner_id for r in restaurants}) == 3

    dishes = list(db.scalars(select(MenuItem)))
    assert len(dishes) >= 15
    assert any(not d.is_available for d in dishes)
    assert any(d.is_available for d in dishes)


def test_seed_orders_cover_every_status_with_consistent_money(db, seeded):
    orders = list(db.scalars(select(Order)))
    by_status = {o.status: o for o in orders}
    assert set(by_status) == {
        OrderStatus.PLACED,
        OrderStatus.ACCEPTED,
        OrderStatus.READY,
        OrderStatus.ASSIGNED,
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
        OrderStatus.REFUNDED,
    }

    for order in orders:
        assert order.total_amount == sum((i.line_total for i in order.items), Decimal("0"))
        for item in order.items:
            assert item.line_total == item.unit_price * item.quantity
        payments = db.scalars(
            select(PaymentLedger).where(
                PaymentLedger.order_id == order.id,
                PaymentLedger.entry_type == LedgerType.PAYMENT,
            )
        ).all()
        assert len(payments) == 1
        assert payments[0].amount == order.total_amount

    refunded = by_status[OrderStatus.REFUNDED]
    refunds = db.scalars(
        select(PaymentLedger).where(
            PaymentLedger.order_id == refunded.id,
            PaymentLedger.entry_type == LedgerType.REFUND,
        )
    ).all()
    assert len(refunds) == 1 and refunds[0].amount == refunded.total_amount

    delivered_review = db.scalar(
        select(Review).where(Review.order_id == by_status[OrderStatus.DELIVERED].id)
    )
    assert delivered_review is not None
    assert delivered_review.restaurant_id == by_status[OrderStatus.DELIVERED].restaurant_id

    placed = by_status[OrderStatus.PLACED]
    age = datetime.now(timezone.utc) - placed.status_updated_at.astimezone(timezone.utc)
    assert timedelta(minutes=29) <= age <= timedelta(minutes=32)


def test_seeded_customer_can_log_in(client, db, seeded):
    customers = [c for c in seeded["credentials"] if c["role"] == Role.CUSTOMER.value]
    assert len(customers) == 2
    assert customers[0]["password"] == DEMO_PASSWORD

    response = client.post(
        "/auth/login", json={"email": customers[0]["email"], "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]
