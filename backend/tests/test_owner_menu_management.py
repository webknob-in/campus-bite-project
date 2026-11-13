"""Unit tests for owner menu management (Req 16.1, 16.4, 16.7, 6.2)."""
from decimal import Decimal

import pytest

from app.models import MenuItem
from tests.factories import make_customer, make_menu_item, make_order, make_owner, make_partner, make_restaurant

URL = "/owner/menu-items"


@pytest.fixture
def owner_ctx(db, auth_headers):
    owner = make_owner(db)
    restaurant = make_restaurant(db, owner)
    db.commit()
    return restaurant, auth_headers(owner)


def test_create_returns_201_in_callers_restaurant(client, owner_ctx):
    restaurant, headers = owner_ctx
    res = client.post(URL, headers=headers, json={"name": "Veg Burger", "price": "99.50"})
    assert res.status_code == 201
    assert res.json()["restaurant_id"] == restaurant.id
    assert res.json()["name"] == "Veg Burger"


def test_delete_returns_204_and_order_item_keeps_snapshot(client, db, owner_ctx):
    restaurant, headers = owner_ctx
    item = make_menu_item(db, restaurant, name="Soup", price="40.00")
    order = make_order(db, items=[(item, 2)], restaurant=restaurant)
    line = order.items[0]
    db.commit()

    assert client.delete(f"{URL}/{item.id}", headers=headers).status_code == 204
    assert db.get(MenuItem, item.id) is None
    db.refresh(line)
    assert line.menu_item_id is None
    assert line.name == "Soup" and line.unit_price == Decimal("40.00")


def test_owner_b_gets_404_on_owner_a_item_and_item_survives(client, db, auth_headers, owner_ctx):
    restaurant, _ = owner_ctx
    item = make_menu_item(db, restaurant, name="Mine")
    owner_b = make_owner(db)
    make_restaurant(db, owner_b)
    db.commit()
    b = auth_headers(owner_b)
    assert client.patch(f"{URL}/{item.id}", headers=b, json={"name": "X"}).status_code == 404
    assert client.patch(f"{URL}/{item.id}/availability", headers=b, json={"is_available": False}).status_code == 404
    assert client.delete(f"{URL}/{item.id}", headers=b).status_code == 404
    db.expire_all()
    kept = db.get(MenuItem, item.id)
    assert kept is not None and kept.name == "Mine" and kept.is_available is True


def test_customer_and_partner_get_403_visitor_401(client, db, auth_headers, owner_ctx):
    restaurant, _ = owner_ctx
    item = make_menu_item(db, restaurant)
    users = (make_customer(db), make_partner(db))
    db.commit()
    for user in users:
        h = auth_headers(user)
        assert client.get(URL, headers=h).status_code == 403
        assert client.post(URL, headers=h, json={"name": "A", "price": 5}).status_code == 403
        assert client.delete(f"{URL}/{item.id}", headers=h).status_code == 403
    assert client.get(URL).status_code == 401


def test_list_scoped_with_search_and_pagination(client, db, owner_ctx):
    restaurant, headers = owner_ctx
    for n in ("Alpha Dosa", "Beta Dosa", "Gamma Idli"):
        make_menu_item(db, restaurant, name=n)
    make_menu_item(db, make_restaurant(db), name="Foreign Dosa")
    db.commit()

    page = client.get(URL, headers=headers).json()
    assert page["total"] == 3 and page["page"] == 1 and page["page_size"] == 10
    assert all(i["restaurant_id"] == restaurant.id for i in page["items"])
    assert client.get(URL, headers=headers, params={"search": "dosa"}).json()["total"] == 2
    p2 = client.get(URL, headers=headers, params={"page": 2, "page_size": 2}).json()
    assert p2["total"] == 3 and len(p2["items"]) == 1


def test_availability_toggle(client, db, owner_ctx):
    restaurant, headers = owner_ctx
    item = make_menu_item(db, restaurant)
    db.commit()
    res = client.patch(f"{URL}/{item.id}/availability", headers=headers, json={"is_available": False})
    assert res.status_code == 200 and res.json()["is_available"] is False
    res = client.patch(f"{URL}/{item.id}/availability", headers=headers, json={"is_available": True})
    assert res.json()["is_available"] is True


@pytest.mark.parametrize("item_id", [987654, 2**31, 99999999999999999999])
def test_unknown_and_huge_ids_404(client, owner_ctx, item_id):
    _, headers = owner_ctx
    assert client.patch(f"{URL}/{item_id}", headers=headers, json={"name": "X"}).status_code == 404
    assert client.patch(f"{URL}/{item_id}/availability", headers=headers, json={"is_available": True}).status_code == 404
    assert client.delete(f"{URL}/{item_id}", headers=headers).status_code == 404


def test_name_length_boundaries(client, owner_ctx):
    _, headers = owner_ctx
    assert client.post(URL, headers=headers, json={"name": "x" * 121, "price": 10}).status_code == 422
    assert client.post(URL, headers=headers, json={"name": "x" * 120, "price": 10}).status_code == 201
