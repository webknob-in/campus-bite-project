"""Smoke tests for POST /orders/{id}/return (Req 15, 40.8)."""

import pytest

from app.models import OrderStatus, ReturnStatus
from tests.factories import make_customer, make_order, make_owner

pytestmark = pytest.mark.usefixtures("client")


def _setup(db, status=OrderStatus.DELIVERED, **kw):
    customer = make_customer(db)
    order = make_order(db, status, customer=customer, **kw)
    db.commit()
    return customer, order


def _post(client, order_id, headers, reason="Food arrived cold"):
    return client.post(f"/orders/{order_id}/return", json={"reason": reason}, headers=headers)


def test_return_happy_path(client, db, auth_headers):
    customer, order = _setup(db)
    r = _post(client, order.id, auth_headers(customer), "  Food arrived cold  ")
    assert r.status_code == 200
    body = r.json()
    assert body["return_status"] == "requested"
    assert body["return_reason"] == "Food arrived cold"
    assert body["return_requested_at"] is not None
    assert body["status"] == "DELIVERED"
    db.refresh(order)
    assert order.return_status == ReturnStatus.requested
    assert order.status == OrderStatus.DELIVERED


@pytest.mark.parametrize("n,code", [(5, 200), (1000, 200), (4, 422), (1001, 422)])
def test_reason_length_boundaries(client, db, auth_headers, n, code):
    customer, order = _setup(db)
    assert _post(client, order.id, auth_headers(customer), "a" * n).status_code == code


@pytest.mark.parametrize("reason", ["", "     ", "  ab  "])
def test_blank_reason_422(client, db, auth_headers, reason):
    customer, order = _setup(db)
    assert _post(client, order.id, auth_headers(customer), reason).status_code == 422


def test_missing_reason_422(client, db, auth_headers):
    customer, order = _setup(db)
    r = client.post(f"/orders/{order.id}/return", json={}, headers=auth_headers(customer))
    assert r.status_code == 422


def test_second_request_409(client, db, auth_headers):
    customer, order = _setup(db)
    h = auth_headers(customer)
    assert _post(client, order.id, h).status_code == 200
    assert _post(client, order.id, h, "Another reason").status_code == 409


@pytest.mark.parametrize("state", ["requested", "approved", "rejected"])
def test_existing_return_any_state_409(client, db, auth_headers, state):
    customer, order = _setup(db, return_status=state)
    assert _post(client, order.id, auth_headers(customer)).status_code == 409


@pytest.mark.parametrize("status", [OrderStatus.PLACED, OrderStatus.REFUNDED, OrderStatus.CANCELLED])
def test_non_delivered_409(client, db, auth_headers, status):
    customer, order = _setup(db, status)
    assert _post(client, order.id, auth_headers(customer)).status_code == 409


def test_other_customer_404(client, db, auth_headers):
    _, order = _setup(db)
    other = make_customer(db)
    db.commit()
    assert _post(client, order.id, auth_headers(other)).status_code == 404


def test_huge_order_id_404(client, db, auth_headers):
    customer, _ = _setup(db)
    assert _post(client, 2**40, auth_headers(customer)).status_code == 404


def test_non_customer_403(client, db, auth_headers):
    _, order = _setup(db)
    owner = make_owner(db)
    db.commit()
    assert _post(client, order.id, auth_headers(owner)).status_code == 403


def test_no_token_401(client, db):
    _, order = _setup(db)
    assert client.post(f"/orders/{order.id}/return", json={"reason": "Food arrived cold"}).status_code == 401
