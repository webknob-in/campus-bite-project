"""Unit tests for delivery partner flows (Req 21.2-21.6, 21.8)."""
from datetime import datetime, timedelta, timezone

from app.models.enums import OrderStatus
from tests.factories import make_customer, make_order, make_owner, make_partner


def _patch(client, headers, oid, status):
    return client.patch(f"/partner/orders/{oid}/status", json={"status": status}, headers=headers)


def test_response_includes_customer_contact_items_and_money_strings(client, db, auth_headers):
    p = make_partner(db)
    cust = make_customer(db, name="Asha Rao", phone="9000011111")
    o = make_order(db, OrderStatus.ASSIGNED, partner=p, customer=cust,
                   delivery_address="Block C, Room 7", delivery_phone="9000022222")
    db.commit()
    h = auth_headers(p)
    for r in (client.get(f"/partner/orders/{o.id}", headers=h),
              client.get("/partner/orders", headers=h)):
        assert r.status_code == 200
        body = r.json()
        d = body if "items" in body and "id" in body else body["items"][0]
        assert d["customer_name"] == "Asha Rao"
        assert d["delivery_phone"] == "9000022222"
        assert d["delivery_address"] == "Block C, Room 7"
        assert len(d["items"]) == 1
        assert d["items"][0]["price"] == "12.50"
        assert d["total_amount"] == "12.50"


def test_list_default_active_only_own_with_envelope(client, db, auth_headers):
    p, other = make_partner(db), make_partner(db)
    a = make_order(db, OrderStatus.ASSIGNED, partner=p)
    b = make_order(db, OrderStatus.OUT_FOR_DELIVERY, partner=p)
    make_order(db, OrderStatus.DELIVERED, partner=p)
    make_order(db, OrderStatus.REFUNDED, partner=p)
    make_order(db, OrderStatus.ASSIGNED, partner=other)
    db.commit()
    h = auth_headers(p)
    body = client.get("/partner/orders", headers=h).json()
    assert {x["id"] for x in body["items"]} == {a.id, b.id}
    assert body["total"] == 2 and body["page"] == 1
    assert "page_size" in body

    r = client.get("/partner/orders?status=OUT_FOR_DELIVERY", headers=h).json()
    assert [x["id"] for x in r["items"]] == [b.id]
    r = client.get("/partner/orders?status=DELIVERED", headers=h).json()
    assert r["total"] == 1
    r = client.get("/partner/orders?page=1&page_size=1", headers=h).json()
    assert len(r["items"]) == 1 and r["total"] == 2


def test_status_flow_sets_delivered_at(client, db, auth_headers):
    p = make_partner(db)
    o = make_order(db, OrderStatus.ASSIGNED, partner=p)
    db.commit()
    h = auth_headers(p)
    r = _patch(client, h, o.id, "OUT_FOR_DELIVERY")
    assert r.status_code == 200 and r.json()["status"] == "OUT_FOR_DELIVERY"
    assert r.json()["delivered_at"] is None
    r = _patch(client, h, o.id, "DELIVERED")
    assert r.status_code == 200 and r.json()["status"] == "DELIVERED"
    assert r.json()["delivered_at"] is not None
    db.refresh(o)
    assert o.status == OrderStatus.DELIVERED and o.delivered_at is not None


def test_skipping_returns_409_and_leaves_order_unchanged(client, db, auth_headers):
    p = make_partner(db)
    o = make_order(db, OrderStatus.ASSIGNED, partner=p)
    db.commit()
    assert _patch(client, auth_headers(p), o.id, "DELIVERED").status_code == 409
    db.refresh(o)
    assert o.status == OrderStatus.ASSIGNED and o.delivered_at is None


def test_other_partner_gets_404_and_order_unchanged(client, db, auth_headers):
    a, b = make_partner(db), make_partner(db)
    o = make_order(db, OrderStatus.ASSIGNED, partner=a)
    db.commit()
    hb = auth_headers(b)
    assert client.get(f"/partner/orders/{o.id}", headers=hb).status_code == 404
    assert _patch(client, hb, o.id, "OUT_FOR_DELIVERY").status_code == 404
    db.refresh(o)
    assert o.status == OrderStatus.ASSIGNED
    assert client.get("/partner/orders", headers=hb).json()["total"] == 0


def test_history_scope_and_order(client, db, auth_headers):
    p, other = make_partner(db), make_partner(db)
    now = datetime.now(timezone.utc)
    t = now - timedelta(hours=1)
    old = make_order(db, OrderStatus.DELIVERED, partner=p, delivered_at=now - timedelta(hours=3))
    tie1 = make_order(db, OrderStatus.DELIVERED, partner=p, delivered_at=t)
    tie2 = make_order(db, OrderStatus.REFUNDED, partner=p, delivered_at=t)
    new = make_order(db, OrderStatus.DELIVERED, partner=p, delivered_at=now)
    make_order(db, OrderStatus.ASSIGNED, partner=p)
    make_order(db, OrderStatus.OUT_FOR_DELIVERY, partner=p)
    make_order(db, OrderStatus.DELIVERED, partner=other, delivered_at=now)
    db.commit()
    body = client.get("/partner/history", headers=auth_headers(p)).json()
    assert [x["id"] for x in body["items"]] == [new.id, tie2.id, tie1.id, old.id]
    assert body["total"] == 4


def test_non_partner_and_anonymous_rejected(client, db, auth_headers):
    c, ow = make_customer(db), make_owner(db)
    p = make_partner(db)
    o = make_order(db, OrderStatus.ASSIGNED, partner=p)
    db.commit()
    for path in ("/partner/orders", "/partner/history", f"/partner/orders/{o.id}"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=auth_headers(c)).status_code == 403
        assert client.get(path, headers=auth_headers(ow)).status_code == 403
    url = f"/partner/orders/{o.id}/status"
    assert client.patch(url, json={"status": "OUT_FOR_DELIVERY"}).status_code == 401
    assert _patch(client, auth_headers(c), o.id, "OUT_FOR_DELIVERY").status_code == 403
    assert _patch(client, auth_headers(ow), o.id, "OUT_FOR_DELIVERY").status_code == 403
