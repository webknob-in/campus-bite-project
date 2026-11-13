"""Smoke tests for owner return decisions (Req 20, 23.2, 40.8)."""

from datetime import datetime, timedelta, timezone

from app.models import OrderStatus
from tests.factories import make_customer, make_order, make_owner, make_partner, make_restaurant


def _setup(db):
    owner = make_owner(db)
    rest = make_restaurant(db, owner)
    db.commit()
    return owner, rest


def _requested(db, rest, customer=None, **kw):
    kw.setdefault("return_status", "requested")
    return make_order(db, OrderStatus.DELIVERED, restaurant=rest, customer=customer, **kw)


def test_list_filter_paging_order(client, db, auth_headers):
    owner, rest = _setup(db)
    now = datetime.now(timezone.utc)
    o1 = _requested(db, rest, return_requested_at=now - timedelta(hours=3))
    o2 = _requested(db, rest, return_requested_at=now - timedelta(hours=1))
    o3 = _requested(db, rest, return_status="rejected", return_requested_at=now - timedelta(hours=2))
    make_order(db, OrderStatus.DELIVERED, restaurant=rest)  # return_status none: excluded
    db.commit()
    h = auth_headers(owner)

    body = client.get("/owner/returns", headers=h).json()
    assert [i["order_id"] for i in body["items"]] == [o2.id, o3.id, o1.id]
    assert body["total"] == 3
    row = body["items"][0]
    assert row["reason"] and row["total_amount"] == "12.50" and row["return_status"] == "requested"
    assert row["customer_name"] and row["requested_at"]

    r = client.get("/owner/returns", params={"status": "requested"}, headers=h).json()
    assert [i["order_id"] for i in r["items"]] == [o2.id, o1.id]
    r = client.get("/owner/returns", params={"page": 2, "page_size": 2}, headers=h).json()
    assert [i["order_id"] for i in r["items"]] == [o1.id] and r["total"] == 3
    assert client.get("/owner/returns", params={"status": "bogus"}, headers=h).status_code == 422


def test_approve_happy_path_and_customer_sees_ledger(client, db, auth_headers):
    owner, rest = _setup(db)
    customer = make_customer(db)
    order = _requested(db, rest, customer=customer)
    db.commit()

    r = client.post(f"/owner/returns/{order.id}/approve", headers=auth_headers(owner))
    assert r.status_code == 200, r.text
    assert r.json()["return_status"] == "approved" and r.json()["status"] == "REFUNDED"
    assert r.json()["payment_status"] == "refunded"

    d = client.get(f"/orders/{order.id}", headers=auth_headers(customer)).json()
    assert d["status"] == "REFUNDED" and d["return_status"] == "approved"
    entries = d["ledger_entries"]
    assert [e["entry_type"] for e in entries] == ["PAYMENT", "REFUND"]
    assert entries[1]["amount"] == d["total_amount"] == "12.50"
    assert entries[1]["transaction_ref"] != entries[0]["transaction_ref"]


def test_reject(client, db, auth_headers):
    owner, rest = _setup(db)
    order = _requested(db, rest)
    db.commit()
    r = client.post(f"/owner/returns/{order.id}/reject", headers=auth_headers(owner))
    assert r.status_code == 200, r.text
    assert r.json()["return_status"] == "rejected" and r.json()["status"] == "DELIVERED"
    assert r.json()["payment_status"] == "mock_paid"
    db.refresh(order, attribute_names=["ledger_entries"])
    assert len(order.ledger_entries) == 1


def test_double_decision_and_non_requested_409(client, db, auth_headers):
    owner, rest = _setup(db)
    order = _requested(db, rest)
    plain = make_order(db, OrderStatus.DELIVERED, restaurant=rest)
    db.commit()
    h = auth_headers(owner)
    assert client.post(f"/owner/returns/{order.id}/approve", headers=h).status_code == 200
    for action in ("approve", "reject"):
        assert client.post(f"/owner/returns/{order.id}/{action}", headers=h).status_code == 409
        assert client.post(f"/owner/returns/{plain.id}/{action}", headers=h).status_code == 409
    db.refresh(order)
    assert order.return_status.value == "approved" and order.status is OrderStatus.REFUNDED


def test_scoping_and_auth(client, db, auth_headers):
    owner, rest = _setup(db)
    other, _ = _setup(db)
    order = _requested(db, rest)
    db.commit()
    url = f"/owner/returns/{order.id}/approve"
    assert client.post(url, headers=auth_headers(other)).status_code == 404
    assert client.post("/owner/returns/99999999999/approve", headers=auth_headers(owner)).status_code == 404
    assert client.post(url, headers=auth_headers(order.customer)).status_code == 403
    assert client.post(url, headers=auth_headers(make_partner(db))).status_code == 403
    assert client.get("/owner/returns", headers=auth_headers(order.customer)).status_code == 403
    assert client.post(url).status_code == 401
    assert client.get("/owner/returns").status_code == 401
