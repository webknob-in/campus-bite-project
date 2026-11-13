"""Self-check of the shared fixtures in ``conftest.py`` and the factories in ``factories.py``."""

from __future__ import annotations

from datetime import timedelta

import jwt
import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.models import (
    AdminReminderLog,
    LedgerType,
    MenuItem,
    Order,
    OrderItem,
    OrderStatus,
    PaymentLedger,
    PaymentStatus,
    Restaurant,
    ReturnStatus,
    Review,
    Role,
    User,
)
from tests.factories import (
    make_customer,
    make_ledger_entry,
    make_menu_item,
    make_order,
    make_partner,
    make_reminder,
    make_restaurant,
    make_review,
    make_user,
)

ALL_MODELS = [User, Restaurant, MenuItem, Order, OrderItem, PaymentLedger, Review, AdminReminderLog]


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_factories_create_consistent_rows_for_all_models(db):
    order = make_order(db, OrderStatus.DELIVERED)
    review = make_review(db, order)
    reminder = make_reminder(db, make_order(db, OrderStatus.PLACED))
    extra_entry = make_ledger_entry(db, order, LedgerType.REFUND)

    for model in ALL_MODELS:
        assert _count(db, model) > 0, model.__name__

    assert {u.role for u in db.scalars(select(User))} == set(Role)
    assert order.restaurant.owner.role is Role.RESTAURANT_OWNER
    assert order.delivery_partner.role is Role.DELIVERY_PARTNER
    assert order.delivered_at is not None
    assert order.total_amount == sum(i.line_total for i in order.items)
    assert all(i.line_total == i.unit_price * i.quantity for i in order.items)
    payments = [e for e in order.ledger_entries if e.entry_type is LedgerType.PAYMENT]
    assert len(payments) == 1 and payments[0].amount == order.total_amount
    assert (review.customer_id, review.restaurant_id) == (order.customer_id, order.restaurant_id)
    assert reminder.restaurant_id == reminder.order.restaurant_id
    assert reminder.status_at_reminder is OrderStatus.PLACED
    assert extra_entry.transaction_ref != payments[0].transaction_ref


def test_refunded_order_has_payment_and_refund_entries(db):
    order = make_order(db, OrderStatus.REFUNDED)
    assert order.payment_status is PaymentStatus.refunded
    assert order.return_status is ReturnStatus.approved
    assert order.delivered_at is not None and order.delivery_partner_id is not None
    kinds = sorted(e.entry_type.value for e in order.ledger_entries)
    assert kinds == ["PAYMENT", "REFUND"]
    assert all(e.amount == order.total_amount for e in order.ledger_entries)


def test_make_order_accepts_explicit_arguments(db):
    customer = make_customer(db)
    partner = make_partner(db)
    restaurant = make_restaurant(db)
    dish = make_menu_item(db, restaurant, price="3.25")
    order = make_order(
        db,
        OrderStatus.ASSIGNED,
        items=[(dish, 3)],
        customer=customer,
        partner=partner,
        restaurant=restaurant,
        return_status=ReturnStatus.requested,
        payment_status=PaymentStatus.mock_paid,
    )
    assert (order.customer_id, order.delivery_partner_id) == (customer.id, partner.id)
    assert order.total_amount == 9.75
    assert order.return_requested_at is not None
    assert make_order(db, OrderStatus.PLACED).delivery_partner_id is None
    assert make_order(db, total="42.00").total_amount == 42


def test_rollback_isolation_part_one(db):
    make_user(db, email="isolation@example.com")
    db.commit()  # commits the savepoint only
    assert _count(db, User) == 1


def test_rollback_isolation_part_two(db):
    assert _count(db, User) == 0


def test_db_example_rolls_back_each_example(db, db_example):
    for _ in range(3):
        with db_example() as session:
            make_user(session)
            session.commit()
            assert _count(session, User) == 1
    with db_example() as session:
        assert _count(session, User) == 0


def test_client_serves_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_auth_headers_token_is_accepted_by_decode_access_token(db, auth_headers):
    user = make_customer(db)
    header = auth_headers(user)["Authorization"]
    assert header.startswith("Bearer ")
    claims = decode_access_token(header.removeprefix("Bearer "), get_settings())
    assert claims["sub"] == str(user.id)
    assert claims["role"] == "CUSTOMER"
    assert "exp" in claims


def test_auth_headers_supports_expired_and_foreign_tokens(db, auth_headers):
    user = make_customer(db)
    settings = get_settings()
    expired = auth_headers(user, expires_in=timedelta(minutes=-1))["Authorization"][7:]
    foreign = auth_headers(user, secret="x" * 40)["Authorization"][7:]
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired, settings)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(foreign, settings)
