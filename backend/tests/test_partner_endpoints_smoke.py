"""Smoke tests for the delivery partner endpoints (Req 21, 40.5)."""
from datetime import datetime, timedelta, timezone

from app.models.enums import OrderStatus
from tests.factories import make_customer, make_order, make_owner, make_partner


def _patch(client, headers, oid, status):
    return client.patch(f"/partner/orders/{oid}/status", json={"status": status}, headers=headers)


def test_list_filter_pagination_and_fields(client, db, auth_headers):
    p, other = make_partner(db), make_partner(db)
    now = datetime.now(timezone.utc)
    a = make_order(db, OrderStatus.ASSIGNED, partner=p, created_at=now - timedelta(minutes=3))
    b = make_order(db, OrderStatus.OUT_FOR_DELIVERY, partner=p, created_at=now - timedelta(minutes=2))
    make_order(db, OrderStatus.DELIVERED, partner=p)
    make_order(db, OrderStatus.ASSIGNED, partner=other)
    db.commit()
    h = auth_headers(p)

    r = client.get("/partner/orders", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2 and [o["id"] for o in body["items"]] == [b.id, a.id]
    o = body["items"][0]
    for k in ("customer_name", "delivery_phone", "delivery_address", "restaurant_name",
              "restaurant_address", "items", "total_amount", "created_at"):
        assert k in o
    assert o["items"][0]["price"] == "12.50" and o["total_amount"] == "12.50"

    r = client.get("/partner/orders?status=ASSIGNED", headers=h)
    assert [x["id"] for x in r.json()["items"]] == [a.id]
    r = client.get("/partner/orders?page=2&page_size=1", headers=h)
    assert r.json()["page"] == 2 and [x["id"] for x in r.json()["items"]] == [a.id]
    assert client.get("/partner/orders?status=BOGUS", headers=h).status_code == 422


def test_detail_own_and_other(client, db, auth_headers):
    p, other = make_partner(db), make_partner(db)
    mine = make_order(db, OrderStatus.ASSIGNED, partner=p)
    theirs = make_order(db, OrderStatus.ASSIGNED, partner=other)
    db.commit()
    h = auth_headers(p)
    assert client.get(f"/partner/orders/{mine.id}", headers=h).json()["id"] == mine.id
    assert client.get(f"/partner/orders/{theirs.id}", headers=h).status_code == 404
    assert client.get("/partner/orders/99999999999", headers=h).status_code == 404
    assert _patch(client, h, theirs.id, "OUT_FOR_DELIVERY").status_code == 404


def test_status_flow_and_invalid_transitions(client, db, auth_headers):
    p = make_partner(db)
    o = make_order(db, OrderStatus.ASSIGNED, partner=p)
    db.commit()
    h = auth_headers(p)

    assert _patch(client, h, o.id, "DELIVERED").status_code == 409
    assert _patch(client, h, o.id, "READY").status_code == 409
    assert _patch(client, h, o.id, "BOGUS").status_code == 422
    r = _patch(client, h, o.id, "OUT_FOR_DELIVERY")
    assert r.status_code == 200 and r.json()["status"] == "OUT_FOR_DELIVERY"
    assert _patch(client, h, o.id, "OUT_FOR_DELIVERY").status_code == 409
    r = _patch(client, h, o.id, "DELIVERED")
    assert r.status_code == 200 and r.json()["delivered_at"] is not None
    assert _patch(client, h, o.id, "DELIVERED").status_code == 409
    db.refresh(o)
    assert o.status == OrderStatus.DELIVERED


def test_history_ordering(client, db, auth_headers):
    p = make_partner(db)
    now = datetime.now(timezone.utc)
    old = make_order(db, OrderStatus.DELIVERED, partner=p, delivered_at=now - timedelta(hours=2))
    new = make_order(db, OrderStatus.REFUNDED, partner=p, delivered_at=now - timedelta(hours=1))
    make_order(db, OrderStatus.ASSIGNED, partner=p)
    db.commit()
    r = client.get("/partner/history", headers=auth_headers(p))
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["items"]] == [new.id, old.id]
    assert r.json()["total"] == 2


def test_auth_failures(client, db, auth_headers):
    c, ow = make_customer(db), make_owner(db)
    db.commit()
    for path in ("/partner/orders", "/partner/history", "/partner/orders/1"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=auth_headers(c)).status_code == 403
        assert client.get(path, headers=auth_headers(ow)).status_code == 403
    assert _patch(client, auth_headers(c), 1, "DELIVERED").status_code == 403
