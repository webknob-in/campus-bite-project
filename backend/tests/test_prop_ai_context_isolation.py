"""Property test for AI context isolation (Requirements 28.1, 28.4, 29.1).

A fake OpenAI client captures the ``messages`` sent for both AI endpoints. The JSON order context
must contain exactly the caller's most recent Orders and nothing belonging to other customers.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.services.ai_service import get_openai_client
from app.services.rate_limiter import reset_ai_limiter
from tests.factories import make_customer, make_order, make_restaurant

BASE_TIME = datetime(2024, 1, 1, tzinfo=timezone.utc)
HEADER = "Order history JSON:\n"
FOOTER = "\n\nQuestion:"


class CapturingClient:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs["messages"])
        msg = type("M", (), {"content": "ok"})()
        return type("C", (), {"choices": [type("Ch", (), {"message": msg})()]})()


def _context(messages: list[dict]) -> tuple[str, dict]:
    text = "\n".join(m["content"] for m in messages)
    user = messages[-1]["content"]
    raw = user[user.index(HEADER) + len(HEADER) : user.index(FOOTER)]
    return text, json.loads(raw)


@st.composite
def scenarios(draw: st.DrawFn) -> dict:
    n_a = draw(st.integers(0, 60))
    n_b = draw(st.integers(0, 6))
    n_c = draw(st.integers(0, 6))
    # Distinct creation times in a random order, so id order differs from time order.
    a_slots = draw(st.permutations(range(n_a)))
    return {"n_a": n_a, "n_b": n_b, "n_c": n_c, "a_slots": list(a_slots)}


@given(scenario=scenarios())
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_ai_context_contains_only_callers_recent_orders(
    client: TestClient, db_example, auth_headers, scenario: dict
) -> None:
    """Feature: campusbite-platform, Property 25: AI context contains only the caller's recent Orders

    **Validates: Requirements 28.1, 28.4, 29.1**
    """
    with db_example() as db:

        def _get_db() -> Iterator[Session]:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

        fake = CapturingClient()
        fastapi_app.dependency_overrides[deps.get_db] = _get_db
        fastapi_app.dependency_overrides[get_openai_client] = lambda: fake
        reset_ai_limiter()
        try:
            tag = uuid.uuid4().hex[:8]
            a = make_customer(db, name=f"ZZ-NAME-A-{tag}", email=f"zz-a-{tag}@example.com")
            b = make_customer(db, name=f"ZZ-NAME-B-{tag}", email=f"zz-b-{tag}@example.com", address=f"ZZ-ADDR-B-{tag}")
            c = make_customer(db, name=f"ZZ-NAME-C-{tag}", email=f"zz-c-{tag}@example.com", address=f"ZZ-ADDR-C-{tag}")
            rest_a = make_restaurant(db, name=f"ZZ-REST-A-{tag}")
            rest_other = make_restaurant(db, name=f"ZZ-REST-OTHER-{tag}")

            a_orders = []
            for i in range(scenario["n_a"]):
                a_orders.append(
                    make_order(
                        db,
                        customer=a,
                        restaurant=rest_a,
                        items=[{"menu_item": None, "name": f"ZZ-ITEM-A-{tag}-{i}", "unit_price": 5}],
                        created_at=BASE_TIME + timedelta(minutes=scenario["a_slots"][i]),
                        with_ledger=False,
                    )
                )
            other_orders = []
            for owner, count in ((b, scenario["n_b"]), (c, scenario["n_c"])):
                for j in range(count):
                    other_orders.append(
                        make_order(
                            db,
                            customer=owner,
                            restaurant=rest_other,
                            items=[{"menu_item": None, "name": f"ZZ-ITEM-O-{tag}-{owner.id}-{j}", "unit_price": 7}],
                            # Newer than every order of A, so a leak would show up in the top-N.
                            created_at=BASE_TIME + timedelta(days=1, minutes=j),
                            with_ledger=False,
                        )
                    )
            db.commit()

            ranked = sorted(a_orders, key=lambda o: (o.created_at, o.id), reverse=True)
            other_ids = {o.id for o in other_orders}
            headers = auth_headers(a)

            for limit, call in (
                (50, lambda: client.post("/ai/insights", json={"question": "what did I order?"}, headers=headers)),
                (5, lambda: client.get("/ai/insights/summary", headers=headers)),
            ):
                reset_ai_limiter()
                fake.calls.clear()
                res = call()
                assert res.status_code == 200, res.text
                expected = ranked[: min(limit, len(ranked))]
                if not expected:
                    assert fake.calls == []
                    assert res.json()["order_count"] == 0
                    continue
                assert len(fake.calls) == 1
                text, ctx = _context(fake.calls[0])
                assert [o["id"] for o in ctx["orders"]] == [o.id for o in expected]
                assert ctx["order_count"] == res.json()["order_count"] == len(expected)
                assert not ({o["id"] for o in ctx["orders"]} & other_ids)
                for o in ctx["orders"]:
                    assert o["restaurant"] == rest_a.name
                assert "ZZ-ITEM-O-" not in text and "ZZ-REST-OTHER" not in text
                for forbidden in (b, c):
                    assert forbidden.name not in text and forbidden.email not in text
                    assert forbidden.address not in text
                assert a.email not in text and a.name not in text
                kept = {o.id for o in expected}
                for order in a_orders:
                    in_ctx = f'"{order.items[0].name}"' in text
                    assert in_ctx == (order.id in kept)
        finally:
            fastapi_app.dependency_overrides.pop(get_openai_client, None)
            reset_ai_limiter()
