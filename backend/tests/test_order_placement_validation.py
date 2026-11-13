"""Unit tests (task 6.9): placement validation, card data handling, cancellation rules, access.

Validates: Requirements 11.8, 11.9, 11.10, 11.11, 12.3, 13.2, 13.3, 23.4
"""
import pytest
from sqlalchemy import Enum, String, Text, func, select

from app.db.base import Base
from app.models import LedgerType, Order, OrderItem, OrderStatus, PaymentLedger
from tests.factories import (
    make_customer,
    make_menu_item,
    make_order,
    make_owner,
    make_partner,
)

CARD = "4111111111111111"
CVV = "737"
PAYMENT = {"card_holder": "Asha Rao", "card_number": CARD, "expiry": "12/99", "cvv": CVV}


def _body(*lines, **overrides) -> dict:
    data = {
        "items": [{"menu_item_id": i, "quantity": q} for i, q in lines],
        "delivery_address": "Hostel 3, Room 12",
        "delivery_phone": "+91 98765 43210",
        "payment": dict(PAYMENT),
    }
    data.update(overrides)
    return data


def _counts(db) -> tuple[int, int, int]:
    return tuple(db.scalar(select(func.count()).select_from(m)) for m in (Order, OrderItem, PaymentLedger))


@pytest.fixture
def customer(db):
    user = make_customer(db)
    db.commit()
    return user


@pytest.mark.parametrize(
    "payment_change",
    [
        {"card_number": "411111111111111"},
        {"card_number": "41111111111111111"},
        {"card_number": "4111a11111111111"},
        {"expiry": "13/99"},
        {"expiry": "00/99"},
        {"expiry": "01/20"},
        {"expiry": "1299"},
        {"cvv": "12"},
        {"cvv": "12345"},
        {"cvv": "12a"},
    ],
)
def test_bad_card_fields_are_422(client, db, customer, auth_headers, payment_change):
    item = make_menu_item(db)
    db.commit()
    body = _body((item.id, 1))
    body["payment"] = {**PAYMENT, **payment_change}
    response = client.post("/orders", json=body, headers=auth_headers(customer))
    assert response.status_code == 422
    assert _counts(db) == (0, 0, 0)


@pytest.mark.parametrize("quantity", [0, 100, -1])
def test_bad_quantity_is_422(client, db, customer, auth_headers, quantity):
    item = make_menu_item(db)
    db.commit()
    response = client.post("/orders", json=_body((item.id, quantity)), headers=auth_headers(customer))
    assert response.status_code == 422
    assert _counts(db) == (0, 0, 0)


def test_empty_items_is_422(client, customer, auth_headers):
    response = client.post("/orders", json=_body(), headers=auth_headers(customer))
    assert response.status_code == 422


@pytest.mark.parametrize("missing", ["delivery_address", "delivery_phone", "payment"])
def test_missing_required_field_is_422(client, db, customer, auth_headers, missing):
    item = make_menu_item(db)
    db.commit()
    body = _body((item.id, 1))
    del body[missing]
    assert client.post("/orders", json=body, headers=auth_headers(customer)).status_code == 422
    assert _counts(db) == (0, 0, 0)


def test_blank_address_is_422(client, db, customer, auth_headers):
    item = make_menu_item(db)
    db.commit()
    body = _body((item.id, 1), delivery_address="   ")
    assert client.post("/orders", json=body, headers=auth_headers(customer)).status_code == 422


def test_ledger_stores_only_last4_and_no_card_number_in_any_text_column(client, db, customer, auth_headers):
    item = make_menu_item(db, price="10.00")
    db.commit()

    response = client.post("/orders", json=_body((item.id, 2)), headers=auth_headers(customer))
    assert response.status_code == 201
    order_id = response.json()["id"]

    ledger_columns = {c.name for c in PaymentLedger.__table__.columns}
    assert "card_last4" in ledger_columns
    assert not {"card_number", "cvv", "expiry", "card_holder"} & ledger_columns
    row = db.scalar(select(PaymentLedger).where(PaymentLedger.order_id == order_id))
    assert row.card_last4 == CARD[-4:]

    # Scan every string column of every table for the full card number and the CVV.
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if not isinstance(column.type, (String, Text)) or isinstance(column.type, Enum):
                continue
            for secret in (CARD, CVV):
                match = column == secret if secret == CVV else column.contains(secret)
                hits = db.scalar(select(func.count()).select_from(table).where(match))
                assert hits == 0, f"{secret!r} found in {table.name}.{column.name}"
    # CARD[-4:] ("1111") is the only card-derived value allowed to be stored.


def test_detail_includes_payment_ledger_entry(client, db, customer, auth_headers):
    item = make_menu_item(db, price="12.50")
    db.commit()
    placed = client.post("/orders", json=_body((item.id, 2)), headers=auth_headers(customer)).json()

    detail = client.get(f"/orders/{placed['id']}", headers=auth_headers(customer)).json()

    (entry,) = detail["ledger_entries"]
    assert entry["entry_type"] == LedgerType.PAYMENT.value
    assert entry["amount"] == detail["total_amount"] == "25.00"
    assert entry["transaction_ref"].startswith("MOCK-")
    assert entry["card_last4"] == CARD[-4:]


@pytest.mark.parametrize(
    "status",
    [OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED, OrderStatus.CANCELLED],
)
def test_cancel_after_placed_is_409_and_order_unchanged(client, db, customer, auth_headers, status):
    order = make_order(db, status, customer=customer)
    db.commit()
    before = (order.status, order.status_updated_at)

    response = client.post(f"/orders/{order.id}/cancel", headers=auth_headers(customer))

    assert response.status_code == 409
    db.expire_all()
    fresh = db.get(Order, order.id)
    assert (fresh.status, fresh.status_updated_at) == before


def test_cancel_placed_works_once_then_409(client, db, customer, auth_headers):
    order = make_order(db, customer=customer)
    db.commit()
    headers = auth_headers(customer)

    first = client.post(f"/orders/{order.id}/cancel", headers=headers)
    assert first.status_code == 200 and first.json()["status"] == "CANCELLED"
    db.expire_all()
    cancelled_at = db.get(Order, order.id).status_updated_at

    assert client.post(f"/orders/{order.id}/cancel", headers=headers).status_code == 409
    db.expire_all()
    assert db.get(Order, order.id).status_updated_at == cancelled_at


def test_other_customer_gets_404_on_detail_and_cancel(client, db, customer, auth_headers):
    stranger = make_customer(db)
    order = make_order(db, customer=customer)
    db.commit()

    assert client.get(f"/orders/{order.id}", headers=auth_headers(stranger)).status_code == 404
    assert client.post(f"/orders/{order.id}/cancel", headers=auth_headers(stranger)).status_code == 404
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.PLACED


def test_owner_and_partner_cannot_place_orders_and_visitor_is_401(client, db, auth_headers):
    owner = make_owner(db)
    partner = make_partner(db)
    item = make_menu_item(db)
    db.commit()
    body = _body((item.id, 1))

    assert client.post("/orders", json=body, headers=auth_headers(owner)).status_code == 403
    assert client.post("/orders", json=body, headers=auth_headers(partner)).status_code == 403
    assert client.post("/orders", json=body).status_code == 401
    assert _counts(db) == (0, 0, 0)
