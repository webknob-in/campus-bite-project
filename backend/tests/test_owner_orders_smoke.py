"""Smoke tests for the owner order endpoints (Req 17, 18)."""
from datetime import datetime, timedelta, timezone

from app.models import OrderStatus
from tests.factories import make_customer, make_order, make_owner, make_partner, make_restaurant


def _setup(db):
    owner = make_owner(db)
    rest = make_restaurant(db, owner)
    db.commit()
    return owner, rest


def test_list_filters_and_pagination(client, db, auth_headers):
    owner, rest = _setup(db)
    now = datetime.now(timezone.utc)
    cust = make_customer(db, name="Alice")
    o1 = make_order(db, restaurant=rest, customer=cust, created_at=now - timedelta(days=3))
    o2 = make_order(db, OrderStatus.ACCEPTED, restaurant=rest, customer=cust, created_at=now - timedelta(days=1))
    o3 = make_order(db, restaurant=rest, customer=cust, created_at=now)
    make_order(db)  # foreign restaurant
    db.commit()
    h = auth_headers(owner)

    body = client.get("/owner/orders", headers=h).json()
    assert [i["id"] for i in body["items"]] == [o3.id, o2.id, o1.id]
    assert body["total"] == 3
    row = body["items"][0]
    assert row["customer_name"] == "Alice"
    assert row["total_amount"] == "12.50"
    assert row["items"][0]["price"] == "12.50" and row["delivery_partner"] is None

    r = client.get("/owner/orders", params={"status": "ACCEPTED"}, headers=h).json()
    assert [i["id"] for i in r["items"]] == [o2.id]
    d = (now - timedelta(days=2)).date().isoformat()
    r = client.get("/owner/orders", params={"date_from": d}, headers=h).json()
    assert r["total"] == 2
    r = client.get("/owner/orders", params={"page": 2, "page_size": 2}, headers=h).json()
    assert [i["id"] for i in r["items"]] == [o1.id] and r["total"] == 3
    assert client.get("/owner/orders", params={"status": "NOPE"}, headers=h).status_code == 422


def test_status_flow_and_invalid_transitions(client, db, auth_headers):
    owner, rest = _setup(db)
    order = make_order(db, restaurant=rest)
    db.commit()
    h = auth_headers(owner)
    url = f"/owner/orders/{order.id}/status"

    assert client.patch(url, json={"status": "READY"}, headers=h).status_code == 409
    for s in ("ACCEPTED", "PREPARING", "READY"):
        r = client.patch(url, json={"status": s}, headers=h)
        assert r.status_code == 200 and r.json()["status"] == s
    for s in ("CANCELLED", "ASSIGNED", "DELIVERED", "PLACED"):
        assert client.patch(url, json={"status": s}, headers=h).status_code == 409
    assert client.patch(url, json={"status": "bogus"}, headers=h).status_code == 422
    db.refresh(order)
    assert order.status == OrderStatus.READY


def test_assign_and_failures(client, db, auth_headers):
    owner, rest = _setup(db)
    partner = make_partner(db, name="Pat")
    ready = make_order(db, OrderStatus.READY, restaurant=rest)
    placed = make_order(db, restaurant=rest)
    db.commit()
    h = auth_headers(owner)

    r = client.get("/owner/delivery-partners", headers=h).json()
    assert partner.id in [p["id"] for p in r["items"]] and "total" in r and r["page"] == 1

    other = make_customer(db)
    db.commit()
    url = f"/owner/orders/{ready.id}/assign"
    assert client.post(url, json={"delivery_partner_id": other.id}, headers=h).status_code == 400
    assert client.post(url, json={"delivery_partner_id": 10**12}, headers=h).status_code == 400
    assert client.post(
        f"/owner/orders/{placed.id}/assign", json={"delivery_partner_id": partner.id}, headers=h
    ).status_code == 409

    r = client.post(url, json={"delivery_partner_id": partner.id}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "ASSIGNED"
    assert r.json()["delivery_partner"] == {"id": partner.id, "name": "Pat"}
    assert client.post(url, json={"delivery_partner_id": partner.id}, headers=h).status_code == 409


def test_foreign_and_missing_orders_404(client, db, auth_headers):
    owner, _ = _setup(db)
    foreign = make_order(db)
    db.commit()
    h = auth_headers(owner)
    for oid in (foreign.id, 10**15):
        assert client.patch(f"/owner/orders/{oid}/status", json={"status": "ACCEPTED"}, headers=h).status_code == 404
        assert client.post(f"/owner/orders/{oid}/assign", json={"delivery_partner_id": 1}, headers=h).status_code == 404


def test_auth_and_roles(client, db, auth_headers):
    cust, partner = make_customer(db), make_partner(db)
    db.commit()
    calls = [
        ("get", "/owner/orders", None),
        ("get", "/owner/delivery-partners", None),
        ("patch", "/owner/orders/1/status", {"status": "ACCEPTED"}),
        ("post", "/owner/orders/1/assign", {"delivery_partner_id": 1}),
    ]
    for method, url, body in calls:
        kw = {"json": body} if body else {}
        assert getattr(client, method)(url, **kw).status_code == 401
        for u in (cust, partner):
            assert getattr(client, method)(url, headers=auth_headers(u), **kw).status_code == 403
