"""Smoke tests for the public browsing endpoints (Req 8, 9, 40.2). Formal tests: tasks 4.4-4.7."""
from datetime import datetime, timedelta, timezone

import pytest

from tests.factories import make_menu_item, make_order, make_restaurant, make_review
from app.models import OrderStatus


def test_restaurant_list_search_rating_and_detail(client, db):
    pizza = make_restaurant(db, name="Zed Pizza Hub", cuisine="Italian")
    curry = make_restaurant(db, name="Spice Route", cuisine="Indian")
    make_review(db, make_order(db, OrderStatus.DELIVERED, restaurant=pizza), rating=5)
    make_review(db, make_order(db, OrderStatus.DELIVERED, restaurant=pizza), rating=4)

    body = client.get("/restaurants", params={"search": "ZED PIZ"}).json()
    assert [r["id"] for r in body["items"]] == [pizza.id]
    assert body["items"][0]["average_rating"] == 4.5
    assert body["items"][0]["review_count"] == 2
    assert {"name", "description", "cuisine", "address", "image_url", "is_open"} <= body["items"][0].keys()

    by_cuisine = client.get("/restaurants", params={"search": "indian"}).json()
    assert [r["id"] for r in by_cuisine["items"]] == [curry.id]
    assert by_cuisine["items"][0]["average_rating"] is None
    assert by_cuisine["items"][0]["review_count"] == 0

    detail = client.get(f"/restaurants/{pizza.id}")
    assert detail.status_code == 200 and detail.json()["average_rating"] == 4.5
    assert client.get("/restaurants/99999999").status_code == 404
    assert client.get("/restaurants/99999999999").status_code == 404
    assert client.get("/restaurants/abc").status_code == 422


def test_search_matches_wildcards_literally(client, db):
    literal = make_restaurant(db, name="100% Veg_Cafe", cuisine="Indian")
    make_restaurant(db, name="1000 Vegan Cafe", cuisine="Indian")
    for text in ("100%", "Veg_C"):
        ids = [r["id"] for r in client.get("/restaurants", params={"search": text}).json()["items"]]
        assert ids == [literal.id]
    assert client.get("/restaurants", params={"search": "\\"}).json()["total"] == 0
    assert client.get("/restaurants", params={"search": "a\x00b"}).status_code == 200


def test_restaurant_pagination_is_ordered_and_complete(client, db):
    for _ in range(5):
        make_restaurant(db, name="Same Name Grill")
    seen, total = [], None
    for page in (1, 2, 3):
        body = client.get(
            "/restaurants", params={"search": "Same Name", "page": page, "page_size": 2}
        ).json()
        total = body["total"]
        seen += [r["id"] for r in body["items"]]
        assert (body["page"], body["page_size"]) == (page, 2)
    assert total == 5 and seen == sorted(seen) and len(set(seen)) == 5
    assert client.get("/restaurants", params={"page": 0}).status_code == 422
    assert client.get("/restaurants", params={"page_size": 101}).status_code == 422


def test_menu_filters_and_money_format(client, db):
    r = make_restaurant(db)
    cheap = make_menu_item(db, r, name="Veg Roll", price="49.5")
    mid = make_menu_item(db, r, name="Paneer Roll", price="100")
    off = make_menu_item(db, r, name="Egg Roll", price="150.00", is_available=False)
    make_menu_item(db, make_restaurant(db), name="Other Roll", price="60")

    menu = client.get(f"/restaurants/{r.id}/menu").json()
    assert [i["id"] for i in menu["items"]] == [off.id, mid.id, cheap.id]  # name asc
    assert menu["total"] == 3
    prices = {i["id"]: i["price"] for i in menu["items"]}
    assert prices == {cheap.id: "49.50", mid.id: "100.00", off.id: "150.00"}
    assert next(i for i in menu["items"] if i["id"] == off.id)["is_available"] is False
    assert {"name", "description", "price", "category", "image_url", "is_available"} <= menu["items"][0].keys()

    def ids(**params):
        body = client.get(f"/restaurants/{r.id}/menu", params=params).json()
        return {i["id"] for i in body["items"]}

    assert ids(search="ROLL", min_price="50") == {mid.id, off.id}
    assert ids(max_price="100") == {cheap.id, mid.id}
    assert ids(min_price="100", max_price="100") == {mid.id}
    assert ids(search="paneer", min_price="10", max_price="120") == {mid.id}
    assert ids(search="nothing") == set()
    assert client.get("/restaurants/99999999/menu").status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"min_price": "-1"},
        {"max_price": "-0.01"},
        {"min_price": "abc"},
        {"max_price": "NaN"},
        {"min_price": "10", "max_price": "9.99"},
    ],
)
def test_invalid_price_filters_return_422(client, db, params):
    r = make_restaurant(db)
    assert client.get(f"/restaurants/{r.id}/menu", params=params).status_code == 422
    response = client.get("/dishes", params=params)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_dishes_span_restaurants_with_restaurant_info(client, db):
    a = make_restaurant(db, name="Alpha Kitchen")
    b = make_restaurant(db, name="Beta Kitchen")
    d1 = make_menu_item(db, a, name="Zzq Biryani", price="120")
    d2 = make_menu_item(db, b, name="zzq biryani", price="80")
    soup = make_menu_item(db, b, name="Zzq Soup", price="30")

    body = client.get("/dishes", params={"search": "ZZQ BIR"}).json()
    assert {i["id"]: (i["restaurant_id"], i["restaurant_name"]) for i in body["items"]} == {
        d1.id: (a.id, "Alpha Kitchen"),
        d2.id: (b.id, "Beta Kitchen"),
    }
    assert body["total"] == 2
    cheap = client.get("/dishes", params={"search": "zzq", "max_price": "80"}).json()
    assert {i["id"] for i in cheap["items"]} == {d2.id, soup.id}
    paged = client.get("/dishes", params={"search": "zzq", "page_size": 1, "page": 3}).json()
    assert paged["total"] == 3 and len(paged["items"]) == 1


def test_reviews_newest_first_and_paginated(client, db):
    r = make_restaurant(db)
    now = datetime.now(timezone.utc)
    reviews = [
        make_review(
            db,
            make_order(db, OrderStatus.DELIVERED, restaurant=r),
            rating=3,
            created_at=now - timedelta(days=d),
        )
        for d in (3, 1, 2)
    ]
    body = client.get(f"/restaurants/{r.id}/reviews").json()
    assert [i["id"] for i in body["items"]] == [reviews[1].id, reviews[2].id, reviews[0].id]
    assert {"rating", "comment", "created_at", "customer_name"} <= body["items"][0].keys()
    page2 = client.get(f"/restaurants/{r.id}/reviews", params={"page": 2, "page_size": 2}).json()
    assert page2["total"] == 3 and [i["id"] for i in page2["items"]] == [reviews[0].id]
    assert client.get("/restaurants/99999999/reviews").status_code == 404
