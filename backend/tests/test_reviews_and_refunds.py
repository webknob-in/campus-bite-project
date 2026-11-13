"""Unit tests for reviews and refunds end to end (Req 8.6, 14.1, 20.1, 23.3, 23.4)."""

import pytest

from app.models import OrderStatus
from tests.factories import make_customer, make_order, make_owner, make_restaurant

pytestmark = pytest.mark.usefixtures("client")


def _owner_rest(db):
    owner = make_owner(db)
    rest = make_restaurant(db, owner)
    db.commit()
    return owner, rest


def _return_request(client, order_id, headers, reason="Food arrived cold"):
    return client.post(f"/orders/{order_id}/return", json={"reason": reason}, headers=headers)


# ------------------------------------------------------------------ reviews


def test_review_listed_newest_first_with_aggregates(client, db, auth_headers):
    _, rest = _owner_rest(db)
    c1 = make_customer(db, name="Alice A")
    c2 = make_customer(db, name="Bob B")
    o1 = make_order(db, OrderStatus.DELIVERED, restaurant=rest, customer=c1)
    o2 = make_order(db, OrderStatus.DELIVERED, restaurant=rest, customer=c2)
    db.commit()

    assert client.get(f"/restaurants/{rest.id}").json()["review_count"] == 0
    assert client.get(f"/restaurants/{rest.id}").json()["average_rating"] is None

    r1 = client.post(f"/orders/{o1.id}/review", json={"rating": 5, "comment": "Great"}, headers=auth_headers(c1))
    r2 = client.post(f"/orders/{o2.id}/review", json={"rating": 2}, headers=auth_headers(c2))
    assert r1.status_code == 201 and r2.status_code == 201

    body = client.get(f"/restaurants/{rest.id}/reviews").json()
    assert [i["id"] for i in body["items"]] == [r2.json()["id"], r1.json()["id"]]
    first, second = body["items"]
    assert (first["customer_name"], first["rating"], first["comment"]) == ("Bob B", 2, None)
    assert (second["customer_name"], second["rating"], second["comment"]) == ("Alice A", 5, "Great")

    detail = client.get(f"/restaurants/{rest.id}").json()
    assert detail["review_count"] == 2
    assert detail["average_rating"] == 3.5


def test_review_shown_in_order_detail(client, db, auth_headers):
    customer = make_customer(db)
    order = make_order(db, OrderStatus.DELIVERED, customer=customer)
    db.commit()
    h = auth_headers(customer)
    assert client.post(f"/orders/{order.id}/review", json={"rating": 4, "comment": "ok"}, headers=h).status_code == 201
    review = client.get(f"/orders/{order.id}", headers=h).json()["review"]
    assert review["rating"] == 4 and review["comment"] == "ok"


# ------------------------------------------------------------------ refunds


def test_full_refund_flow(client, db, auth_headers):
    owner, rest = _owner_rest(db)
    customer = make_customer(db)
    order = make_order(db, OrderStatus.DELIVERED, restaurant=rest, customer=customer)
    db.commit()
    ch, oh = auth_headers(customer), auth_headers(owner)

    assert _return_request(client, order.id, ch).status_code == 200

    listing = client.get("/owner/returns", params={"status": "requested"}, headers=oh).json()
    assert [i["order_id"] for i in listing["items"]] == [order.id]

    r = client.post(f"/owner/returns/{order.id}/approve", headers=oh)
    assert r.status_code == 200, r.text

    d = client.get(f"/orders/{order.id}", headers=ch).json()
    assert d["status"] == "REFUNDED"
    assert d["payment_status"] == "refunded"
    assert d["return_status"] == "approved"
    entries = d["ledger_entries"]
    assert [e["entry_type"] for e in entries] == ["PAYMENT", "REFUND"]
    assert entries[0]["amount"] == entries[1]["amount"] == d["total_amount"]

    owner_rows = client.get("/owner/orders", headers=oh).json()["items"]
    row = next(i for i in owner_rows if i["id"] == order.id)
    assert row["status"] == "REFUNDED"
    assert row["payment_status"] == "refunded"
    assert row["return_status"] == "approved"

    # A refunded order can still be reviewed.
    rv = client.post(f"/orders/{order.id}/review", json={"rating": 3}, headers=ch)
    assert rv.status_code == 201


def test_reject_flow_keeps_delivered_without_refund(client, db, auth_headers):
    owner, rest = _owner_rest(db)
    customer = make_customer(db)
    order = make_order(db, OrderStatus.DELIVERED, restaurant=rest, customer=customer)
    db.commit()
    ch = auth_headers(customer)

    assert _return_request(client, order.id, ch).status_code == 200
    assert client.post(f"/owner/returns/{order.id}/reject", headers=auth_headers(owner)).status_code == 200

    d = client.get(f"/orders/{order.id}", headers=ch).json()
    assert d["status"] == "DELIVERED"
    assert d["return_status"] == "rejected"
    assert d["payment_status"] == "mock_paid"
    assert [e["entry_type"] for e in d["ledger_entries"]] == ["PAYMENT"]


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_other_owner_gets_404_and_order_unchanged(client, db, auth_headers, action):
    _, rest_a = _owner_rest(db)
    owner_b, _ = _owner_rest(db)
    order = make_order(db, OrderStatus.DELIVERED, restaurant=rest_a, return_status="requested")
    db.commit()

    r = client.post(f"/owner/returns/{order.id}/{action}", headers=auth_headers(owner_b))
    assert r.status_code == 404

    db.refresh(order)
    assert order.status is OrderStatus.DELIVERED
    assert order.return_status.value == "requested"
    assert order.payment_status.value == "mock_paid"
    db.refresh(order, attribute_names=["ledger_entries"])
    assert len(order.ledger_entries) == 1


# ------------------------------------------------------------------ returns list


def test_returns_list_filters_by_status_pages_and_scopes(client, db, auth_headers):
    owner, rest = _owner_rest(db)
    _, other_rest = _owner_rest(db)
    req = [make_order(db, OrderStatus.DELIVERED, restaurant=rest, return_status="requested") for _ in range(3)]
    appr = make_order(db, OrderStatus.REFUNDED, restaurant=rest)
    rej = make_order(db, OrderStatus.DELIVERED, restaurant=rest, return_status="rejected")
    make_order(db, OrderStatus.DELIVERED, restaurant=rest)  # no return
    foreign = make_order(db, OrderStatus.DELIVERED, restaurant=other_rest, return_status="requested")
    db.commit()
    h = auth_headers(owner)

    def ids(**params):
        body = client.get("/owner/returns", params=params, headers=h).json()
        return {i["order_id"] for i in body["items"]}, body

    got, body = ids(status="requested")
    assert got == {o.id for o in req} and body["total"] == 3
    assert ids(status="approved")[0] == {appr.id}
    assert ids(status="rejected")[0] == {rej.id}

    all_ids, body = ids()
    assert foreign.id not in all_ids and body["total"] == 5

    p1, b1 = ids(status="requested", page=1, page_size=2)
    p2, b2 = ids(status="requested", page=2, page_size=2)
    assert len(p1) == 2 and len(p2) == 1 and not p1 & p2
    assert b1["total"] == b2["total"] == 3

    assert client.get("/owner/returns", params={"status": "bogus"}, headers=h).status_code == 422
