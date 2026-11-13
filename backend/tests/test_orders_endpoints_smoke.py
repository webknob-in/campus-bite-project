"""HTTP smoke tests of the customer order endpoints (task 6.4) and the 422 sanitizer."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.errors import sanitize_validation_errors
from app.models import LedgerType, Order, OrderItem, OrderStatus, PaymentLedger, PaymentStatus
from tests.factories import (
    make_customer,
    make_menu_item,
    make_order,
    make_owner,
    make_partner,
    make_restaurant,
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
    return tuple(
        db.scalar(select(func.count()).select_from(model)) for model in (Order, OrderItem, PaymentLedger)
    )


@pytest.fixture
def customer(db):
    user = make_customer(db)
    db.commit()
    return user


# ------------------------------------------------------------------------------ POST /orders


def test_place_order_happy_path(client, db, customer, auth_headers):
    restaurant = make_restaurant(db)
    a = make_menu_item(db, restaurant, price="12.34")
    b = make_menu_item(db, restaurant, price="0.10")
    db.commit()

    response = client.post("/orders", json=_body((a.id, 3), (b.id, 7)), headers=auth_headers(customer))

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "PLACED"
    assert data["payment_status"] == "mock_paid"
    assert data["total_amount"] == "37.72"
    assert data["restaurant_id"] == restaurant.id and data["restaurant_name"] == restaurant.name
    assert {(i["name"], i["quantity"]) for i in data["items"]} == {(a.name, 3), (b.name, 7)}
    (entry,) = data["ledger_entries"]
    assert entry["entry_type"] == "PAYMENT"
    assert entry["transaction_ref"].startswith("MOCK-")
    assert entry["card_last4"] == CARD[-4:]
    assert entry["amount"] == "37.72"

    assert CARD not in response.text and "cvv" not in response.text and "card_number" not in response.text
    row = db.scalar(select(PaymentLedger).where(PaymentLedger.order_id == data["id"]))
    assert row.entry_type is LedgerType.PAYMENT and row.card_last4 == CARD[-4:]
    stored = db.get(Order, data["id"])
    assert stored.payment_status is PaymentStatus.mock_paid
    stored_text = " ".join(
        str(v)
        for v in (row.transaction_ref, row.card_last4, row.status, stored.delivery_address, stored.delivery_phone)
    )
    assert CARD not in stored_text and CVV not in stored_text

    assert client.get(f"/orders/{data['id']}", headers=auth_headers(customer)).json()["id"] == data["id"]


@pytest.mark.parametrize(
    "payment_change",
    [
        {"card_number": "411111111111111"},
        {"card_number": "4111-1111-1111-111"},
        {"expiry": "13/99"},
        {"expiry": "01/20"},
        {"cvv": "98765"},
        {"cvv": "9x"},
    ],
)
def test_bad_payment_is_422_and_values_are_not_echoed(client, db, customer, auth_headers, payment_change):
    item = make_menu_item(db)
    db.commit()
    body = _body((item.id, 1))
    body["payment"] = {**PAYMENT, **payment_change}

    response = client.post("/orders", json=body, headers=auth_headers(customer))

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    for secret in (*payment_change.values(), CARD, "98765"):
        assert secret not in response.text
    assert all("input" not in err for err in response.json()["detail"])
    assert _counts(db) == (0, 0, 0)


@pytest.mark.parametrize("items", [[], [{"menu_item_id": 1, "quantity": 0}], [{"menu_item_id": 1, "quantity": 100}]])
def test_bad_items_are_422(client, db, customer, auth_headers, items):
    response = client.post("/orders", json=_body(items=items), headers=auth_headers(customer))
    assert response.status_code == 422
    assert CARD not in response.text and CVV not in response.text


def test_missing_sibling_field_does_not_echo_the_card(client, customer, auth_headers):
    body = _body((1, 1))
    del body["delivery_address"]
    response = client.post("/orders", json=body, headers=auth_headers(customer))
    assert response.status_code == 422
    assert CARD not in response.text and CVV not in response.text
    no_payment = _body((1, 1))
    del no_payment["payment"]
    assert client.post("/orders", json=no_payment, headers=auth_headers(customer)).status_code == 422


def test_unavailable_closed_and_multi_restaurant_are_400_and_create_nothing(client, db, customer, auth_headers):
    restaurant = make_restaurant(db)
    good = make_menu_item(db, restaurant)
    unavailable = make_menu_item(db, restaurant, is_available=False)
    other = make_menu_item(db)
    closed_item = make_menu_item(db, make_restaurant(db, is_open=False))
    db.commit()
    headers = auth_headers(customer)

    for lines in (
        [(unavailable.id, 1)],
        [(good.id, 1), (unavailable.id, 1)],
        [(good.id, 1), (2**40, 1)],
        [(good.id, 1), (other.id, 1)],
        [(closed_item.id, 1)],
    ):
        response = client.post("/orders", json=_body(*lines), headers=headers)
        assert response.status_code == 400, lines
        assert isinstance(response.json()["detail"], str)
        assert _counts(db) == (0, 0, 0)

    # merged duplicate lines above 99 are a 422
    assert client.post("/orders", json=_body((good.id, 60), (good.id, 60)), headers=headers).status_code == 422
    assert _counts(db) == (0, 0, 0)


# -------------------------------------------------------------------------- GET /orders/me


def test_list_my_orders_filters_paging_and_order(client, db, customer, auth_headers):
    other = make_customer(db)
    now = datetime.now(timezone.utc)
    old = make_order(db, customer=customer, created_at=now - timedelta(days=10))
    mid = make_order(db, OrderStatus.DELIVERED, customer=customer, created_at=now - timedelta(days=5))
    new = make_order(db, customer=customer, created_at=now - timedelta(days=1))
    make_order(db, customer=other)
    db.commit()
    headers = auth_headers(customer)

    page = client.get("/orders/me", headers=headers).json()
    assert [o["id"] for o in page["items"]] == [new.id, mid.id, old.id]
    assert (page["total"], page["page"], page["page_size"]) == (3, 1, 10)
    assert page["items"][0]["items"] and "ledger_entries" not in page["items"][0]

    only = client.get("/orders/me", params={"status": "DELIVERED"}, headers=headers).json()
    assert [o["id"] for o in only["items"]] == [mid.id]

    paged = client.get("/orders/me", params={"page": 2, "page_size": 2}, headers=headers).json()
    assert [o["id"] for o in paged["items"]] == [old.id] and paged["total"] == 3

    day = (now - timedelta(days=5)).date().isoformat()
    on_day = client.get("/orders/me", params={"date_from": day, "date_to": day}, headers=headers).json()
    assert [o["id"] for o in on_day["items"]] == [mid.id]

    assert client.get("/orders/me", params={"status": "NOPE"}, headers=headers).status_code == 422
    assert client.get("/orders/me", params={"page": 0}, headers=headers).status_code == 422
    assert (
        client.get("/orders/me", params={"date_from": "2024-03-11", "date_to": "2024-03-10"}, headers=headers).status_code
        == 422
    )


def test_me_is_not_parsed_as_an_order_id(client, customer, auth_headers):
    headers = auth_headers(customer)
    assert client.get("/orders/me", headers=headers).json() == {"items": [], "total": 0, "page": 1, "page_size": 10}
    assert client.get("/orders/abc", headers=headers).status_code == 422


# ------------------------------------------------------------------------- GET /orders/{id}


def test_order_detail_own_other_and_unknown(client, db, customer, auth_headers):
    stranger = make_customer(db)
    order = make_order(db, customer=customer)
    db.commit()

    own = client.get(f"/orders/{order.id}", headers=auth_headers(customer))
    assert own.status_code == 200
    body = own.json()
    assert body["id"] == order.id
    assert body["items"] and len(body["ledger_entries"]) == 1
    assert body["review"] is None and body["delivery_partner_name"] is None

    assert client.get(f"/orders/{order.id}", headers=auth_headers(stranger)).status_code == 404
    assert client.get("/orders/999999", headers=auth_headers(customer)).status_code == 404
    assert client.get(f"/orders/{2**40}", headers=auth_headers(customer)).status_code == 404


# ------------------------------------------------------------------ POST /orders/{id}/cancel


def test_cancel_placed_order(client, db, customer, auth_headers):
    order = make_order(db, customer=customer)
    db.commit()

    response = client.post(f"/orders/{order.id}/cancel", headers=auth_headers(customer))

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert response.json()["id"] == order.id and response.json()["ledger_entries"]
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.CANCELLED
    assert client.post(f"/orders/{order.id}/cancel", headers=auth_headers(customer)).status_code == 409


def test_cancel_accepted_is_409_and_unchanged(client, db, customer, auth_headers):
    order = make_order(db, OrderStatus.ACCEPTED, customer=customer)
    db.commit()

    response = client.post(f"/orders/{order.id}/cancel", headers=auth_headers(customer))

    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.ACCEPTED


def test_cancel_other_customers_or_unknown_order_is_404(client, db, customer, auth_headers):
    stranger = make_customer(db)
    order = make_order(db, customer=stranger)
    db.commit()

    assert client.post(f"/orders/{order.id}/cancel", headers=auth_headers(customer)).status_code == 404
    assert client.post(f"/orders/{2**40}/cancel", headers=auth_headers(customer)).status_code == 404
    db.expire_all()
    assert db.get(Order, order.id).status is OrderStatus.PLACED


# --------------------------------------------------------------------------------- access


def test_non_customers_are_403_and_visitors_401(client, db, auth_headers):
    owner = make_owner(db)
    partner = make_partner(db)
    db.commit()
    routes = [
        ("post", "/orders", {"json": _body((1, 1))}),
        ("get", "/orders/me", {}),
        ("get", "/orders/1", {}),
        ("post", "/orders/1/cancel", {}),
    ]
    for method, path, kwargs in routes:
        for user in (owner, partner):
            response = getattr(client, method)(path, headers=auth_headers(user), **kwargs)
            assert response.status_code == 403, (method, path)
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 401, (method, path)
        assert response.headers["www-authenticate"] == "Bearer"


# ------------------------------------------------------------------------------- sanitizer


def test_sanitizer_blanks_payment_and_password_and_keeps_other_errors():
    errors = [
        {"type": "string_pattern_mismatch", "loc": ("body", "payment", "card_number"), "msg": "m",
         "input": CARD, "ctx": {"pattern": "^\\d{16}$"}},
        {"type": "string_too_short", "loc": ("body", "password"), "msg": "m", "input": "hunter2", "ctx": {"min_length": 8}},
        {"type": "missing", "loc": ("body", "delivery_address"), "msg": "m",
         "input": {"payment": dict(PAYMENT), "password": "hunter2", "items": [1]}},
        {"type": "int_parsing", "loc": ("query", "page"), "msg": "m", "input": "abc"},
    ]
    first, second, third, fourth = sanitize_validation_errors(errors)
    assert "input" not in first and "ctx" not in first and first["loc"] == ("body", "payment", "card_number")
    assert "input" not in second and "ctx" not in second
    assert third["input"] == {"payment": "[redacted]", "password": "[redacted]", "items": [1]}
    assert fourth == errors[3]
    assert errors[0]["input"] == CARD  # the originals are not modified


def test_sanitizer_output_is_json_safe_for_non_finite_floats():
    import json

    from fastapi.encoders import jsonable_encoder

    errors = [{"type": "missing", "loc": ("body", "x"), "msg": "m", "input": {"price": float("nan"), "n": [float("inf")]}}]
    json.dumps(jsonable_encoder(sanitize_validation_errors(errors)), allow_nan=False)


def test_non_finite_json_body_gives_422_not_500(client, customer, auth_headers):
    raw = '{"items": [{"menu_item_id": NaN, "quantity": Infinity}], "payment": {"card_number": "1"}}'
    response = client.post(
        "/orders", content=raw, headers={**auth_headers(customer), "Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert "1" != CARD and CARD not in response.text
