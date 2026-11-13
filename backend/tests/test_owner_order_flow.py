"""Unit tests for the owner order flow (Req 17.4, 18.1, 18.2, 18.5)."""
from app.models import OrderStatus
from tests.factories import make_customer, make_order, make_owner, make_partner, make_restaurant


def _setup(db):
    owner = make_owner(db)
    rest = make_restaurant(db, owner)
    db.commit()
    return owner, rest


def _status_in_list(client, h, order_id):
    items = client.get("/owner/orders", headers=h).json()["items"]
    return next(i["status"] for i in items if i["id"] == order_id)


def test_full_status_flow_visible_in_list(client, db, auth_headers):
    owner, rest = _setup(db)
    order = make_order(db, restaurant=rest)
    db.commit()
    h = auth_headers(owner)
    assert _status_in_list(client, h, order.id) == "PLACED"
    for s in ("ACCEPTED", "PREPARING", "READY"):
        r = client.patch(f"/owner/orders/{order.id}/status", json={"status": s}, headers=h)
        assert r.status_code == 200 and r.json()["status"] == s
        assert _status_in_list(client, h, order.id) == s


def test_skipping_and_disallowed_targets_conflict_unchanged(client, db, auth_headers):
    owner, rest = _setup(db)
    order = make_order(db, restaurant=rest)
    db.commit()
    h = auth_headers(owner)
    url = f"/owner/orders/{order.id}/status"
    assert client.patch(url, json={"status": "PREPARING"}, headers=h).status_code == 409
    for s in ("CANCELLED", "DELIVERED", "ASSIGNED"):
        assert client.patch(url, json={"status": s}, headers=h).status_code == 409
    db.refresh(order)
    assert order.status == OrderStatus.PLACED


def test_assign_one_partner_to_two_ready_orders(client, db, auth_headers):
    owner, rest = _setup(db)
    partner = make_partner(db)
    o1 = make_order(db, OrderStatus.READY, restaurant=rest)
    o2 = make_order(db, OrderStatus.READY, restaurant=rest)
    db.commit()
    h = auth_headers(owner)
    for o in (o1, o2):
        r = client.post(
            f"/owner/orders/{o.id}/assign", json={"delivery_partner_id": partner.id}, headers=h
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ASSIGNED" and r.json()["delivery_partner"]["id"] == partner.id


def test_assign_failures(client, db, auth_headers):
    owner, rest = _setup(db)
    partner = make_partner(db)
    cust = make_customer(db)
    other_owner = make_owner(db)
    placed = make_order(db, restaurant=rest)
    ready = make_order(db, OrderStatus.READY, restaurant=rest)
    db.commit()
    h = auth_headers(owner)
    assert client.post(
        f"/owner/orders/{placed.id}/assign", json={"delivery_partner_id": partner.id}, headers=h
    ).status_code == 409
    url = f"/owner/orders/{ready.id}/assign"
    for bad in (cust.id, other_owner.id, 10**12):
        assert client.post(url, json={"delivery_partner_id": bad}, headers=h).status_code == 400
    db.refresh(ready)
    assert ready.status == OrderStatus.READY


def test_other_owner_gets_404(client, db, auth_headers):
    owner_a, rest_a = _setup(db)
    owner_b, _ = _setup(db)
    partner = make_partner(db)
    order = make_order(db, OrderStatus.READY, restaurant=rest_a)
    db.commit()
    hb = auth_headers(owner_b)
    assert client.patch(
        f"/owner/orders/{order.id}/status", json={"status": "ACCEPTED"}, headers=hb
    ).status_code == 404
    assert client.post(
        f"/owner/orders/{order.id}/assign", json={"delivery_partner_id": partner.id}, headers=hb
    ).status_code == 404
    db.refresh(order)
    assert order.status == OrderStatus.READY


def test_delivery_partner_list_only_partners_with_paging(client, db, auth_headers):
    owner, _ = _setup(db)
    partners = [make_partner(db, name=f"P{i}") for i in range(3)]
    make_customer(db, name="Cust")
    make_owner(db)
    db.commit()
    h = auth_headers(owner)
    body = client.get("/owner/delivery-partners", headers=h).json()
    assert {i["id"] for i in body["items"]} == {p.id for p in partners}
    assert body["total"] == 3
    p1 = client.get("/owner/delivery-partners", params={"page": 1, "page_size": 2}, headers=h).json()
    p2 = client.get("/owner/delivery-partners", params={"page": 2, "page_size": 2}, headers=h).json()
    assert len(p1["items"]) == 2 and len(p2["items"]) == 1
    assert {i["id"] for i in p1["items"] + p2["items"]} == {p.id for p in partners}
