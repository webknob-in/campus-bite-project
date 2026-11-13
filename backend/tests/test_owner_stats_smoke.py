"""Smoke tests for GET /owner/stats (Req 19.1-19.3)."""

from datetime import datetime, timedelta, timezone

from app.models import LedgerType, OrderStatus
from app.services.stats_service import restaurant_stats
from tests.factories import (
    make_customer,
    make_ledger_entry,
    make_menu_item,
    make_order,
    make_partner,
    make_restaurant,
    make_review,
)


def _get(client, db, auth_headers, owner):
    db.commit()
    return client.get("/owner/stats", headers=auth_headers(owner))


def test_empty_restaurant_returns_zeros(client, db, auth_headers):
    r = make_restaurant(db)
    owner = db.get(type(r.owner), r.owner_id)
    resp = _get(client, db, auth_headers, owner)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_orders"] == 0 and body["orders_today"] == 0
    assert body["net_revenue"] == "0.00"
    assert body["average_rating"] is None
    assert body["top_dishes"] == []
    assert set(body["status_counts"]) == {s.value for s in OrderStatus}
    assert all(v == 0 for v in body["status_counts"].values())


def test_mixed_statuses_and_refund_revenue(client, db, auth_headers):
    r = make_restaurant(db)
    item = make_menu_item(db, r, price="10.00")
    make_order(db, OrderStatus.PLACED, restaurant=r, items=[item])
    make_order(db, OrderStatus.PLACED, restaurant=r, items=[item])
    make_order(db, OrderStatus.DELIVERED, restaurant=r, items=[(item, 2)])  # 20.00
    make_order(db, OrderStatus.REFUNDED, restaurant=r, items=[item])  # +10 -10
    body = _get(client, db, auth_headers, r.owner).json()
    assert body["total_orders"] == 4
    assert body["status_counts"]["PLACED"] == 2
    assert body["status_counts"]["DELIVERED"] == 1
    assert body["status_counts"]["REFUNDED"] == 1
    assert body["status_counts"]["CANCELLED"] == 0
    assert body["net_revenue"] == "40.00"  # 10+10+20+10 - 10


def test_refund_reduces_revenue(client, db, auth_headers):
    r = make_restaurant(db)
    o = make_order(db, OrderStatus.DELIVERED, restaurant=r, total="30.00")
    make_ledger_entry(db, o, LedgerType.REFUND, amount="5.25")
    assert _get(client, db, auth_headers, r.owner).json()["net_revenue"] == "24.75"


def test_today_vs_yesterday_utc_boundary(db):
    r = make_restaurant(db)
    now = datetime(2024, 5, 10, 12, 0, tzinfo=timezone.utc)
    midnight = datetime(2024, 5, 10, tzinfo=timezone.utc)
    make_order(db, restaurant=r, created_at=midnight)
    make_order(db, restaurant=r, created_at=midnight - timedelta(microseconds=1))
    make_order(db, restaurant=r, created_at=midnight + timedelta(days=1))
    stats = restaurant_stats(db, r.id, now)
    assert stats.total_orders == 3
    assert stats.orders_today == 1


def test_average_rating(client, db, auth_headers):
    r = make_restaurant(db)
    for rating in (5, 4, 4):
        make_review(db, make_order(db, OrderStatus.DELIVERED, restaurant=r), rating=rating)
    assert _get(client, db, auth_headers, r.owner).json()["average_rating"] == 4.33


def test_top_five_dishes_cut_and_tiebreak(client, db, auth_headers):
    r = make_restaurant(db)
    specs = {"Fff": 1, "Eee": 2, "Ddd": 3, "Bbb": 3, "Ccc": 3, "Aaa": 10}
    items = [{"menu_item": None, "name": n, "unit_price": "1.00", "quantity": q} for n, q in specs.items()]
    make_order(db, OrderStatus.DELIVERED, restaurant=r, items=items)
    top = _get(client, db, auth_headers, r.owner).json()["top_dishes"]
    assert top == [
        {"name": "Aaa", "quantity": 10},
        {"name": "Bbb", "quantity": 3},
        {"name": "Ccc", "quantity": 3},
        {"name": "Ddd", "quantity": 3},
        {"name": "Eee", "quantity": 2},
    ]


def test_other_restaurant_data_excluded(client, db, auth_headers):
    mine = make_restaurant(db)
    other = make_restaurant(db)
    make_order(db, OrderStatus.DELIVERED, restaurant=mine, items=[{"menu_item": None, "name": "Mine", "quantity": 1}])
    o = make_order(db, OrderStatus.DELIVERED, restaurant=other, items=[{"menu_item": None, "name": "Theirs", "quantity": 9}])
    make_review(db, o, rating=1)
    body = _get(client, db, auth_headers, mine.owner).json()
    assert body["total_orders"] == 1
    assert body["average_rating"] is None
    assert body["net_revenue"] == "10.00"
    assert [d["name"] for d in body["top_dishes"]] == ["Mine"]


def test_customer_and_partner_forbidden_and_no_token(client, db, auth_headers):
    customer, partner = make_customer(db), make_partner(db)
    db.commit()
    assert client.get("/owner/stats", headers=auth_headers(customer)).status_code == 403
    assert client.get("/owner/stats", headers=auth_headers(partner)).status_code == 403
    assert client.get("/owner/stats").status_code == 401
