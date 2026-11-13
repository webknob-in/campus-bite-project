"""Property test for order placement pricing and payment (Requirements 6.4, 11.1, 11.2, 11.3, 11.5, 23.1, 47.1, 47.2)."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api import deps
from app.db.base import Base
from app.main import app as fastapi_app
from app.models import LedgerType, OrderStatus, PaymentLedger, PaymentStatus
from tests.factories import make_customer, make_menu_item, make_owner, make_restaurant

prices = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("5000.00"), places=2)
card_numbers = st.text(alphabet="0123456789", min_size=16, max_size=16)
cvvs = st.text(alphabet="0123456789", min_size=3, max_size=3)
expiries = st.builds(
    lambda m, y: f"{m:02d}/{y:02d}", st.integers(1, 12), st.integers(60, 99)
)  # always in the future


@st.composite
def carts(draw: st.DrawFn) -> dict:
    n = draw(st.integers(1, 6))
    unit_prices = draw(st.lists(prices, min_size=n, max_size=n))
    # Lines refer to item indexes; a repeated index merges (summed quantity stays <= 99).
    lines: list[tuple[int, int]] = []
    for idx in range(n):
        lines.append((idx, draw(st.integers(1, 99))))
    extra = draw(st.lists(st.integers(0, n - 1), max_size=3))
    for idx in extra:
        used = sum(q for i, q in lines if i == idx)
        if used < 99:
            lines.append((idx, draw(st.integers(1, 99 - used))))
    return {
        "prices": unit_prices,
        "lines": lines,
        "tamper": draw(st.booleans()),
        "card": draw(card_numbers),
        "cvv": draw(cvvs),
        "expiry": draw(expiries),
    }


@given(cart=carts())
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_order_placement_pricing_and_payment(client: TestClient, db_example, auth_headers, cart: dict) -> None:
    """Feature: campusbite-platform, Property 11: Order placement pricing and payment

    **Validates: Requirements 6.4, 11.1, 11.2, 11.3, 11.5, 23.1, 47.1, 47.2**
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

        customer = make_customer(db)
        other = make_customer(db)
        restaurant = make_restaurant(db, make_owner(db), is_open=True)
        menu = [make_menu_item(db, restaurant, price=p) for p in cart["prices"]]
        db.commit()

        items = []
        for idx, qty in cart["lines"]:
            line = {"menu_item_id": menu[idx].id, "quantity": qty}
            if cart["tamper"]:
                line["price"] = "0.01"
                line["unit_price"] = "0.01"
            items.append(line)
        body = {
            "items": items,
            "delivery_address": "Hostel 1, Room 101",
            "delivery_phone": "9876543210",
            "payment": {
                "card_holder": "Test Student",
                "card_number": cart["card"],
                "expiry": cart["expiry"],
                "cvv": cart["cvv"],
            },
        }
        if cart["tamper"]:
            body["total"] = "0.01"
            body["total_amount"] = "0.01"
            body["customer_id"] = other.id

        res = client.post("/orders", json=body, headers=auth_headers(customer))
        assert res.status_code == 201, res.text
        data = res.json()

        # Independent expected values (merged quantities).
        merged: dict[int, int] = {}
        for idx, qty in cart["lines"]:
            merged[idx] = merged.get(idx, 0) + qty
        expected_total = sum((cart["prices"][i] * q for i, q in merged.items()), Decimal("0"))
        expected_total_2 = Decimal("0")
        for i in sorted(merged):
            expected_total_2 += Decimal(str(cart["prices"][i])) * merged[i]
        assert expected_total == expected_total_2

        assert data["status"] == OrderStatus.PLACED.value
        assert data["payment_status"] == PaymentStatus.mock_paid.value
        assert Decimal(str(data["total_amount"])) == expected_total
        assert sum(Decimal(str(i["line_total"])) for i in data["items"]) == expected_total

        # Snapshots.
        assert len(data["items"]) == len(merged)
        by_menu = {i["menu_item_id"]: i for i in data["items"]}
        for idx, qty in merged.items():
            snap = by_menu[menu[idx].id]
            assert snap["name"] == menu[idx].name
            assert Decimal(str(snap["unit_price"])) == cart["prices"][idx]
            assert snap["quantity"] == qty
            assert Decimal(str(snap["line_total"])) == cart["prices"][idx] * qty

        # Exactly one PAYMENT ledger entry.
        entries = db.scalars(select(PaymentLedger).where(PaymentLedger.order_id == data["id"])).all()
        assert len(entries) == 1
        entry = entries[0]
        assert entry.entry_type is LedgerType.PAYMENT
        assert entry.amount == expected_total
        assert entry.transaction_ref.startswith("MOCK-")
        assert entry.card_last4 == cart["card"][-4:]
        assert db.scalar(select(func.count()).select_from(PaymentLedger).where(
            PaymentLedger.transaction_ref == entry.transaction_ref)) == 1
        assert len(data["ledger_entries"]) == 1
        assert data["ledger_entries"][0]["transaction_ref"] == entry.transaction_ref

        # Customer is the caller.
        row = db.execute(text("select customer_id from orders where id = :i"), {"i": data["id"]}).scalar_one()
        assert row == customer.id

        # Card number and CVV are never stored or returned.
        assert cart["card"] not in res.text
        for key in ("card_number", "cvv", "expiry", "card_holder"):
            assert key not in data and key not in res.text
        for table in Base.metadata.sorted_tables:
            assert not {"card_number", "cvv"} & {c.name for c in table.columns}
            for r in db.execute(table.select()).all():
                for value in r:
                    assert cart["card"] not in str(value)
                    if isinstance(value, str):
                        assert value != cart["cvv"]
