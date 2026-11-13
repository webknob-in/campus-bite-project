"""Smoke tests for the owner menu endpoints (Req 16, 40.2). Formal tests: tasks 5.2-5.4."""
from decimal import Decimal

import pytest

from app.models import MenuItem
from tests.factories import make_customer, make_menu_item, make_order, make_owner, make_partner, make_restaurant

URL = "/owner/menu-items"


@pytest.fixture
def owner_ctx(db, auth_headers):
    owner = make_owner(db)
    restaurant = make_restaurant(db, owner)
    db.commit()  # an error response makes get_db roll back; keep the setup rows out of that savepoint
    return restaurant, auth_headers(owner)


def test_create_list_search_and_paging(client, db, owner_ctx):
    restaurant, headers = owner_ctx
    other = make_restaurant(db)
    make_menu_item(db, other, name="Foreign Burger")
    db.commit()

    created = client.post(
        URL,
        headers=headers,
        json={"name": "  Veg Burger ", "price": "99.50", "description": "Tasty", "category": "Snacks"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Veg Burger" and body["price"] == "99.50"
    assert body["restaurant_id"] == restaurant.id and body["is_available"] is True
    client.post(URL, headers=headers, json={"name": "Pasta_Red", "price": 120, "is_available": False})
    client.post(URL, headers=headers, json={"name": "Pasta Alfredo", "price": 130.5})

    page = client.get(URL, headers=headers).json()
    assert page["total"] == 3 and page["page"] == 1 and page["page_size"] == 10
    assert [i["name"] for i in page["items"]] == ["Pasta Alfredo", "Pasta_Red", "Veg Burger"]

    assert client.get(URL, headers=headers, params={"search": "PASTA_"}).json()["total"] == 1
    assert client.get(URL, headers=headers, params={"search": "burger"}).json()["total"] == 1
    paged = client.get(URL, headers=headers, params={"page": 2, "page_size": 2}).json()
    assert paged["total"] == 3 and [i["name"] for i in paged["items"]] == ["Veg Burger"]
    assert client.get(URL, headers=headers, params={"page_size": 101}).status_code == 422


def test_patch_updates_only_supplied_fields(client, db, owner_ctx):
    restaurant, headers = owner_ctx
    item = make_menu_item(db, restaurant, name="Dosa", price="50.00", description="Crispy", category="South")
    db.commit()

    res = client.patch(f"{URL}/{item.id}", headers=headers, json={"price": "60.25"})
    assert res.status_code == 200
    body = res.json()
    assert body["price"] == "60.25" and body["name"] == "Dosa"
    assert body["description"] == "Crispy" and body["category"] == "South" and body["is_available"] is True

    cleared = client.patch(f"{URL}/{item.id}", headers=headers, json={"description": None}).json()
    assert cleared["description"] is None and cleared["price"] == "60.25"
    assert client.patch(f"{URL}/{item.id}", headers=headers, json={}).json()["name"] == "Dosa"

    for field in ("name", "price", "is_available"):
        assert client.patch(f"{URL}/{item.id}", headers=headers, json={field: None}).status_code == 422


def test_availability_toggle(client, db, owner_ctx):
    restaurant, headers = owner_ctx
    item = make_menu_item(db, restaurant)
    db.commit()
    res = client.patch(f"{URL}/{item.id}/availability", headers=headers, json={"is_available": False})
    assert res.status_code == 200 and res.json()["is_available"] is False
    res = client.patch(f"{URL}/{item.id}/availability", headers=headers, json={"is_available": True})
    assert res.json()["is_available"] is True
    for bad in ({}, {"is_available": None}, {"is_available": "maybe"}):
        assert client.patch(f"{URL}/{item.id}/availability", headers=headers, json=bad).status_code == 422


def test_delete_keeps_order_item_snapshots(client, db, owner_ctx):
    restaurant, headers = owner_ctx
    item = make_menu_item(db, restaurant, name="Soup", price="40.00")
    order = make_order(db, items=[(item, 2)], restaurant=restaurant)
    line = order.items[0]
    db.commit()

    assert client.delete(f"{URL}/{item.id}", headers=headers).status_code == 204
    assert db.get(MenuItem, item.id) is None
    db.refresh(line)
    assert line.menu_item_id is None
    assert line.name == "Soup" and line.unit_price == Decimal("40.00") and line.quantity == 2
    assert client.delete(f"{URL}/{item.id}", headers=headers).status_code == 404


def test_foreign_unknown_and_huge_ids_are_404(client, db, owner_ctx):
    _, headers = owner_ctx
    foreign = make_menu_item(db, make_restaurant(db), name="Theirs")
    db.commit()
    for item_id in (foreign.id, 987654, 2**31, 99999999999999999999):
        assert client.patch(f"{URL}/{item_id}", headers=headers, json={"name": "X"}).status_code == 404
        assert client.patch(f"{URL}/{item_id}/availability", headers=headers, json={"is_available": False}).status_code == 404
        assert client.delete(f"{URL}/{item_id}", headers=headers).status_code == 404
    db.expire_all()
    assert db.get(MenuItem, foreign.id).name == "Theirs"
    assert client.patch(f"{URL}/abc", headers=headers, json={"name": "X"}).status_code == 422


def test_roles_and_authentication(client, db, auth_headers, owner_ctx):
    restaurant, _ = owner_ctx
    item = make_menu_item(db, restaurant)
    users = (make_customer(db), make_partner(db))
    db.commit()
    for user in users:
        headers = auth_headers(user)
        assert client.get(URL, headers=headers).status_code == 403
        assert client.post(URL, headers=headers, json={"name": "A", "price": 5}).status_code == 403
        assert client.patch(f"{URL}/{item.id}", headers=headers, json={"name": "B"}).status_code == 403
        assert client.patch(f"{URL}/{item.id}/availability", headers=headers, json={"is_available": False}).status_code == 403
        assert client.delete(f"{URL}/{item.id}", headers=headers).status_code == 403
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={"name": "A", "price": 5}).status_code == 401
    assert client.delete(f"{URL}/{item.id}").status_code == 401


@pytest.mark.parametrize(
    "price",
    [0, "0", "0.00", -1, "-5.50", "12.345", 100000.01, "100001", "NaN", "Infinity", "-Infinity", "abc", "", True, False, None, [], {}],
)
def test_invalid_price_is_422(client, owner_ctx, price):
    _, headers = owner_ctx
    assert client.post(URL, headers=headers, json={"name": "Dish", "price": price}).status_code == 422


@pytest.mark.parametrize("price", ["0.01", 1, "100000", "100000.00", 12.5, "7.1"])
def test_valid_prices(client, owner_ctx, price):
    _, headers = owner_ctx
    assert client.post(URL, headers=headers, json={"name": "Dish", "price": price}).status_code == 201


@pytest.mark.parametrize("name", ["", "   ", "x" * 121, None, 5, ["a"]])
def test_invalid_name_is_422(client, owner_ctx, name):
    _, headers = owner_ctx
    assert client.post(URL, headers=headers, json={"name": name, "price": 10}).status_code == 422


def test_other_invalid_fields_and_boundaries(client, owner_ctx):
    _, headers = owner_ctx
    assert client.post(URL, headers=headers, json={"name": "x" * 120, "price": 10}).status_code == 201
    assert client.post(URL, headers=headers, json={"price": 10}).status_code == 422
    assert client.post(URL, headers=headers, json={"name": "A"}).status_code == 422
    assert client.post(URL, headers=headers, json={"name": "A", "price": 1, "is_available": "yes"}).status_code == 422
    assert client.post(URL, headers=headers, json={"name": "A", "price": 1, "description": "d" * 1001}).status_code == 422
    assert client.post(URL, headers=headers, json={"name": "A", "price": 1, "image_url": "not a url"}).status_code == 422
    ok = client.post(URL, headers=headers, json={"name": "A", "price": 1, "image_url": "https://x.test/a.png"})
    assert ok.status_code == 201 and ok.json()["image_url"] == "https://x.test/a.png"
