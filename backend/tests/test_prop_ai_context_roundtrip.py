"""Property 26: AI context round trip.

Feature: campusbite-platform, Property 26: AI context round trip
**Validates: Requirements 28.5**
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models.enums import OrderStatus, PaymentStatus, ReturnStatus
from app.services.ai_service import build_context
from tests.factories import make_customer, make_menu_item, make_order, make_restaurant

# Postgres text cannot hold NUL; surrogates cannot be encoded.
_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
    min_size=1,
    max_size=40,
).filter(lambda s: "zqpii" not in s.lower())
_tricky = st.sampled_from(['say "hi"', "back\\slash", "line1\nline2", "tab\there", "日本語 🍜", "é\u2028x"])
_name = st.one_of(_text, _tricky)
_money = st.decimals(min_value=0, max_value=9999, places=2)
_when = st.datetimes(
    min_value=datetime(2020, 1, 1), max_value=datetime(2035, 1, 1), timezones=st.just(timezone.utc)
)
_item = st.fixed_dictionaries(
    {"name": _name, "quantity": st.integers(1, 20), "unit_price": _money}
)
_order = st.fixed_dictionaries(
    {
        "status": st.sampled_from(list(OrderStatus)),
        "payment_status": st.sampled_from(list(PaymentStatus)),
        "return_status": st.sampled_from(list(ReturnStatus)),
        "restaurant": _name,
        "items": st.lists(_item, min_size=1, max_size=4),
        "total": _money,
        "created_at": _when,
        "delivered_at": st.one_of(st.none(), _when),
    }
)

_PII = {
    "email": "zqpii-mail@secret-example.test",
    "name": "Zqpii Fullname Secretson",
    "phone": "9zqpii0011",
    "address": "Zqpii Secret Lane 42",
}
_CARD = "4111111111111111"


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(orders=st.lists(_order, min_size=0, max_size=8), today=st.dates(date(2020, 1, 1), date(2040, 1, 1)))
def test_ai_context_round_trip(db_example, orders, today):
    with db_example() as db:
        customer = make_customer(
            db, name=_PII["name"], email=_PII["email"], phone=_PII["phone"], address=_PII["address"]
        )
        built = []
        for spec in orders:
            restaurant = make_restaurant(db, name=spec["restaurant"])
            order = make_order(
                db,
                spec["status"],
                customer=customer,
                restaurant=restaurant,
                items=[dict(i) for i in spec["items"]],
                total=None,
                payment_status=spec["payment_status"],
                return_status=spec["return_status"],
                created_at=spec["created_at"],
                delivered_at=spec["delivered_at"],
                delivery_address=_PII["address"],
                delivery_phone=_PII["phone"],
                with_ledger=False,
            )
            order.total_amount = spec["total"]
            db.flush()
            built.append((spec, order))

        objs = [o for _, o in built]
        text = build_context(objs, today)
        data = json.loads(text)

        assert data["today"] == today.isoformat()
        assert data["order_count"] == len(objs)
        assert len(data["orders"]) == len(objs)
        for (spec, o), got in zip(built, data["orders"]):
            assert got["id"] == o.id
            assert got["restaurant"] == spec["restaurant"]
            assert got["status"] == spec["status"].value
            assert got["payment_status"] == spec["payment_status"].value
            assert got["return_status"] == spec["return_status"].value
            assert got["total"] == float(Decimal(spec["total"]))
            assert datetime.fromisoformat(got["created_at"]) == spec["created_at"]
            if spec["delivered_at"] is None:
                assert got["delivered_at"] is None
            else:
                assert datetime.fromisoformat(got["delivered_at"]) == spec["delivered_at"]
            assert len(got["items"]) == len(spec["items"])
            by_name = sorted(
                (i["name"], i["quantity"], float(i["unit_price"])) for i in spec["items"]
            )
            got_items = sorted((i["name"], i["qty"], i["unit_price"]) for i in got["items"])
            assert got_items == by_name

        # Fixed point: re-serialising the parsed structure parses back to the same value.
        again = json.loads(json.dumps(data, separators=(",", ":")))
        assert again == data

        lowered = text.lower()
        for value in (*_PII.values(), _CARD):
            assert value.lower() not in lowered
        assert "card" not in {k for od in data["orders"] for k in od}


def test_empty_context_example(db_example):
    with db_example():
        data = json.loads(build_context([], date(2025, 1, 2)))
    assert data == {"today": "2025-01-02", "order_count": 0, "orders": []}
