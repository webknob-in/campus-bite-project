"""Property test: rejected orders leave no trace (Requirements 11.6, 11.7, 47.4).

Each example builds a small catalogue (two open restaurants, one closed), posts a cart with one
invalid element through ``POST /orders`` and checks the rejection, that no table changed, and that
the response does not echo the card number or CVV. The control (same cart without the invalid
element) must then succeed with 201.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import deps
from app.db.base import Base
from app.main import app as fastapi_app
from tests.factories import make_customer, make_menu_item, make_owner, make_restaurant

ITEM_KINDS = ["missing", "huge", "unavailable", "closed", "cross"]
SCHEMA_KINDS = [
    "qty0",
    "qty100",
    "empty",
    "short_address",
    "bad_phone",
    "bad_card",
    "short_card",
    "bad_expiry",
    "past_expiry",
    "bad_cvv",
]
KINDS = ITEM_KINDS + SCHEMA_KINDS

digits = st.text(alphabet="0123456789", min_size=16, max_size=16)
cvvs = st.text(alphabet="0123456789", min_size=3, max_size=3)


def _counts(db: Session) -> dict[str, int]:
    return {t.name: db.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables}


def _payload(items: list[dict], card: str, cvv: str) -> dict:
    return {
        "items": items,
        "delivery_address": "Hostel 1, Room 101",
        "delivery_phone": "9876543210",
        "payment": {"card_holder": "Test Student", "card_number": card, "expiry": "12/99", "cvv": cvv},
    }


@given(
    kind=st.sampled_from(KINDS),
    card=digits,
    cvv=cvvs,
    valid_qtys=st.lists(st.integers(1, 5), min_size=1, max_size=3),
    huge_id=st.integers(2**31, 2**70),
    missing_offset=st.integers(1, 10_000),
    bad_text=st.text(alphabet="abcdefXYZ !@#", min_size=0, max_size=6),
    bad_card=st.text(alphabet="0123456789", min_size=1, max_size=15),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_rejected_orders_leave_no_trace(
    client: TestClient,
    db_example,
    auth_headers,
    kind: str,
    card: str,
    cvv: str,
    valid_qtys: list[int],
    huge_id: int,
    missing_offset: int,
    bad_text: str,
    bad_card: str,
) -> None:
    """Feature: campusbite-platform, Property 12: Rejected orders leave no trace

    **Validates: Requirements 11.6, 11.7, 47.4**
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
        rest_a = make_restaurant(db, make_owner(db), is_open=True)
        rest_b = make_restaurant(db, make_owner(db), is_open=True)
        rest_closed = make_restaurant(db, make_owner(db), is_open=False)
        valid = [make_menu_item(db, rest_a) for _ in valid_qtys]
        valid_lines = [{"menu_item_id": m.id, "quantity": q} for m, q in zip(valid, valid_qtys)]
        max_id = max(m.id for m in valid)
        db.commit()
        headers = auth_headers(customer)

        payload = _payload([dict(line) for line in valid_lines], card, cvv)
        control = None  # payload expected to succeed after the rejection
        expected = 400

        if kind == "missing":
            payload["items"].append({"menu_item_id": max_id + missing_offset + 1000, "quantity": 1})
            control = _payload(valid_lines, card, cvv)
        elif kind == "huge":
            payload["items"].append({"menu_item_id": huge_id, "quantity": 1})
            control = _payload(valid_lines, card, cvv)
        elif kind == "unavailable":
            off = make_menu_item(db, rest_a, is_available=False)
            db.commit()
            payload["items"].append({"menu_item_id": off.id, "quantity": 1})
            control = _payload(valid_lines, card, cvv)
        elif kind == "closed":
            closed_item = make_menu_item(db, rest_closed)
            db.commit()
            payload = _payload([{"menu_item_id": closed_item.id, "quantity": 1}], card, cvv)
            control = None
        elif kind == "cross":
            other = make_menu_item(db, rest_b)
            db.commit()
            payload["items"].append({"menu_item_id": other.id, "quantity": 1})
            control = _payload(valid_lines, card, cvv)
        else:
            expected = 422
            control = _payload(valid_lines, card, cvv)
            if kind == "qty0":
                payload["items"][0]["quantity"] = 0
            elif kind == "qty100":
                payload["items"][0]["quantity"] = 100
            elif kind == "empty":
                payload["items"] = []
            elif kind == "short_address":
                payload["delivery_address"] = "abcd"
            elif kind == "bad_phone":
                payload["delivery_phone"] = "12ab"
            elif kind == "bad_card":
                payload["payment"]["card_number"] = bad_card + "x" * (16 - len(bad_card))
            elif kind == "short_card":
                payload["payment"]["card_number"] = bad_card
            elif kind == "bad_expiry":
                payload["payment"]["expiry"] = "13/30"
            elif kind == "past_expiry":
                payload["payment"]["expiry"] = "01/20"
            elif kind == "bad_cvv":
                payload["payment"]["cvv"] = cvv[:2]

        before = _counts(db)
        res = client.post("/orders", json=payload, headers=headers)
        assert res.status_code == expected, (kind, res.status_code, res.text)

        assert _counts(db) == before
        assert db.scalar(select(func.count()).select_from(Base.metadata.tables["orders"])) == 0

        # The detail never echoes the card number or CVV (including a malformed one).
        text = res.text
        sent_card = payload["payment"]["card_number"]
        sent_cvv = payload["payment"]["cvv"]
        assert card not in text
        assert sent_card not in text
        for quoted in (json.dumps(sent_cvv), f"'{sent_cvv}'"):
            assert quoted not in text
        assert json.dumps(cvv) not in text

        # Control: the same cart without the invalid element is accepted.
        if control is not None:
            ok = client.post("/orders", json=control, headers=headers)
            assert ok.status_code == 201, ok.text
            after = _counts(db)
            assert after["orders"] == before["orders"] + 1
            assert after["payment_ledger"] == before["payment_ledger"] + 1
