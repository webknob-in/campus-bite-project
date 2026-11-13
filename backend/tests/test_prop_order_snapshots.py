"""Property test for immutable order item snapshots (Requirements 11.4, 16.4).

Places an order through ``POST /orders``, then edits and deletes the menu items through the owner
routes. The customer's order, the stored ``order_items`` rows and the owner's order list must keep
the original name, unit price, quantity and total.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import MenuItem, OrderItem
from tests.factories import make_customer, make_menu_item, make_owner, make_restaurant

PAYMENT = {"card_holder": "Test User", "card_number": "4242424242424242", "expiry": "12/99", "cvv": "123"}

prices = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("5000"), places=2)
names = st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ", min_size=1, max_size=40).map(
    str.strip
).filter(bool)


@st.composite
def scenarios(draw: st.DrawFn) -> list[dict]:
    n = draw(st.integers(min_value=1, max_value=4))
    return [
        {
            "name": draw(names),
            "price": draw(prices),
            "quantity": draw(st.integers(min_value=1, max_value=5)),
            "new_name": draw(st.none() | names),
            "new_price": draw(st.none() | prices),
            "toggles": draw(st.integers(min_value=0, max_value=3)),
            "delete": draw(st.booleans()),
        }
        for _ in range(n)
    ]


@given(specs=scenarios())
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_order_item_snapshots_are_immutable(client: TestClient, db_example, auth_headers, specs: list[dict]) -> None:
    """Feature: campusbite-platform, Property 13: Order item snapshots are immutable

    **Validates: Requirements 11.4, 16.4**
    """
    with db_example() as db:

        def _get_db() -> Iterator[Session]:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

        fastapi_app.dependency_overrides[deps.get_db] = _get_db

        owner = make_owner(db)
        restaurant = make_restaurant(db, owner)
        customer = make_customer(db)
        items = [make_menu_item(db, restaurant, name=s["name"], price=s["price"]) for s in specs]
        db.commit()
        owner_h, cust_h = auth_headers(owner), auth_headers(customer)

        body = {
            "items": [{"menu_item_id": m.id, "quantity": s["quantity"]} for m, s in zip(items, specs)],
            "delivery_address": "Hostel 1, Room 101",
            "delivery_phone": "9876543210",
            "payment": PAYMENT,
        }
        res = client.post("/orders", json=body, headers=cust_h)
        assert res.status_code == 201, res.text
        placed = res.json()
        order_id = placed["id"]
        expected = [(s["name"], s["price"], s["quantity"]) for s in specs]
        total = Decimal(str(placed["total_amount"]))
        assert total == sum((p * q for _, p, q in expected), Decimal("0"))

        item_ids = [m.id for m in items]
        for m, s in zip(items, specs):
            patch: dict = {}
            if s["new_name"] is not None:
                patch["name"] = s["new_name"]
            if s["new_price"] is not None:
                patch["price"] = str(s["new_price"])
            if patch:
                r = client.patch(f"/owner/menu-items/{m.id}", json=patch, headers=owner_h)
                assert r.status_code == 200, r.text
            for i in range(s["toggles"]):
                r = client.patch(
                    f"/owner/menu-items/{m.id}/availability", json={"is_available": i % 2 == 1}, headers=owner_h
                )
                assert r.status_code == 200, r.text

        deleted = [m.id for m, s in zip(items, specs) if s["delete"]]
        for item_id in deleted:
            r = client.delete(f"/owner/menu-items/{item_id}", headers=owner_h)
            assert r.status_code == 204, r.text

        db.expire_all()

        def check(rows: list[tuple[str, Decimal, int]]) -> None:
            assert rows == expected

        # Customer view.
        res = client.get(f"/orders/{order_id}", headers=cust_h)
        assert res.status_code == 200, res.text
        got = res.json()
        assert Decimal(str(got["total_amount"])) == total
        check([(i["name"], Decimal(str(i["unit_price"])), i["quantity"]) for i in got["items"]])
        assert [i["menu_item_id"] for i in got["items"]] == [None if i in deleted else i for i in item_ids]

        # Stored rows.
        rows = db.scalars(select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)).all()
        check([(r.name, r.unit_price, r.quantity) for r in rows])
        for r, item_id in zip(rows, item_ids):
            assert r.menu_item_id == (None if item_id in deleted else item_id)
        assert db.scalar(select(MenuItem).where(MenuItem.id.in_(deleted)).limit(1)) is None if deleted else True

        # Owner view.
        res = client.get("/owner/orders", headers=owner_h)
        assert res.status_code == 200, res.text
        row = next(o for o in res.json()["items"] if o["id"] == order_id)
        assert Decimal(str(row["total_amount"])) == total
        check([(i["name"], Decimal(str(i["price"])), i["quantity"]) for i in row["items"]])
