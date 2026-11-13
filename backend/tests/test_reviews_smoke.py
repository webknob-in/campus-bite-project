"""Smoke tests for POST /orders/{id}/review (Req 14, 40.7)."""

import pytest

from app.models import OrderStatus
from tests.factories import make_customer, make_order, make_owner

pytestmark = pytest.mark.usefixtures("client")


def _setup(db, status=OrderStatus.DELIVERED):
    customer = make_customer(db)
    order = make_order(db, status, customer=customer)
    db.commit()
    return customer, order


@pytest.mark.parametrize("status", [OrderStatus.DELIVERED, OrderStatus.REFUNDED])
def test_review_happy_path(client, db, auth_headers, status):
    customer, order = _setup(db, status)
    r = client.post(
        f"/orders/{order.id}/review",
        json={"rating": 4, "comment": "  tasty  "},
        headers=auth_headers(customer),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["rating"] == 4 and body["comment"] == "tasty"
    assert body["restaurant_id"] == order.restaurant_id
    assert body["customer_id"] == customer.id

    detail = client.get(f"/orders/{order.id}", headers=auth_headers(customer)).json()
    assert detail["review"]["rating"] == 4
    listing = client.get(f"/restaurants/{order.restaurant_id}/reviews").json()
    assert [x["id"] for x in listing["items"]] == [body["id"]]


def test_review_placed_order_409(client, db, auth_headers):
    customer, order = _setup(db, OrderStatus.PLACED)
    r = client.post(f"/orders/{order.id}/review", json={"rating": 5}, headers=auth_headers(customer))
    assert r.status_code == 409


def test_duplicate_review_409(client, db, auth_headers):
    customer, order = _setup(db)
    h = auth_headers(customer)
    assert client.post(f"/orders/{order.id}/review", json={"rating": 5}, headers=h).status_code == 201
    assert client.post(f"/orders/{order.id}/review", json={"rating": 3}, headers=h).status_code == 409


def test_other_customer_404(client, db, auth_headers):
    _, order = _setup(db)
    other = make_customer(db)
    db.commit()
    r = client.post(f"/orders/{order.id}/review", json={"rating": 5}, headers=auth_headers(other))
    assert r.status_code == 404


def test_huge_order_id_404(client, db, auth_headers):
    customer, _ = _setup(db)
    r = client.post(f"/orders/{2**40}/review", json={"rating": 5}, headers=auth_headers(customer))
    assert r.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"rating": 0},
        {"rating": 6},
        {"rating": 4.5},
        {"rating": "5"},
        {"rating": True},
        {"rating": 5, "comment": "x" * 1001},
    ],
)
def test_invalid_payload_422(client, db, auth_headers, payload):
    customer, order = _setup(db)
    r = client.post(f"/orders/{order.id}/review", json=payload, headers=auth_headers(customer))
    assert r.status_code == 422


def test_non_customer_403(client, db, auth_headers):
    _, order = _setup(db)
    owner = make_owner(db)
    db.commit()
    r = client.post(f"/orders/{order.id}/review", json={"rating": 5}, headers=auth_headers(owner))
    assert r.status_code == 403
