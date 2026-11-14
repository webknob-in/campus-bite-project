"""Property test for restaurant statistics (Requirements 19.1, 19.2, 19.3).

Each example builds a restaurant with random orders and reviews, plus a second restaurant whose data
must be ignored, calls ``GET /owner/stats`` and compares every field with an independent pure-Python
model. "Today" is the current UTC date; timestamps are generated relative to a ``now`` captured
before the example and the example is discarded (``assume``) if the UTC date changed while it ran,
so the property cannot flake around midnight.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import OrderStatus
from tests.factories import make_order, make_owner, make_restaurant, make_review

# Plain alphabetic names so that SQL collation and Python ordering agree on "name ascending".
DISH_NAMES = ["Burger", "Dosa", "Idli", "Naan", "Pizza", "Samosa", "Tea", "Wrap"]
STATUSES = list(OrderStatus)

line_st = st.tuples(
    st.sampled_from(DISH_NAMES),
    st.integers(min_value=1, max_value=5),
    st.integers(min_value=1, max_value=50000),  # unit price in cents
)
# age: None = today (now); otherwise hours before the start of today (yesterday or older).
order_st = st.fixed_dictionaries(
    {
        "status": st.sampled_from(STATUSES),
        "age_hours": st.one_of(st.none(), st.integers(min_value=1, max_value=24 * 10)),
        "lines": st.lists(line_st, min_size=1, max_size=3),
        "rating": st.one_of(st.none(), st.integers(min_value=1, max_value=5)),
    }
)
orders_st = st.lists(order_st, min_size=0, max_size=15)


def _lines(lines: list[tuple[str, int, int]]) -> list[dict]:
    return [
        {"menu_item": None, "name": n, "quantity": q, "unit_price": Decimal(c) / 100}
        for n, q, c in lines
    ]


def _build(db: Session, owner_specs: list[dict], now: datetime) -> dict:
    """Persist the specs for one restaurant and return the independent model's expectation."""
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    status_counts = {s.value: 0 for s in OrderStatus}
    orders_today = 0
    net = Decimal("0.00")
    ratings: list[int] = []
    qty: dict[str, int] = defaultdict(int)
    return {
        "specs": owner_specs,
        "day_start": day_start,
        "status_counts": status_counts,
        "orders_today": orders_today,
        "net": net,
        "ratings": ratings,
        "qty": qty,
    }


def _populate(db: Session, restaurant, specs: list[dict], now: datetime, model: dict | None) -> None:
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for spec in specs:
        created_at = now if spec["age_hours"] is None else day_start - timedelta(hours=spec["age_hours"])
        order = make_order(
            db, spec["status"], restaurant=restaurant, items=_lines(spec["lines"]), created_at=created_at
        )
        if spec["rating"] is not None:
            make_review(db, order, rating=spec["rating"])
        if model is None:
            continue
        model["status_counts"][spec["status"].value] += 1
        if day_start <= created_at < day_start + timedelta(days=1):
            model["orders_today"] += 1
        total = sum((Decimal(q) * Decimal(c) / 100 for _, q, c in spec["lines"]), Decimal("0.00"))
        model["net"] += total
        if spec["status"] is OrderStatus.REFUNDED:
            model["net"] -= total
        if spec["rating"] is not None:
            model["ratings"].append(spec["rating"])
        for name, q, _ in spec["lines"]:
            model["qty"][name] += q


@given(mine=orders_st, other=orders_st)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_restaurant_statistics_match_model(
    client: TestClient, db_example, auth_headers, mine: list[dict], other: list[dict]
) -> None:
    """Feature: campusbite-platform, Property 22: Restaurant statistics match model

    **Validates: Requirements 19.1, 19.2, 19.3**

    ``/owner/stats`` returns total orders, orders created today (UTC), net revenue (PAYMENT minus
    REFUND ledger amounts), the 2-place average rating (null without reviews), zero-filled counts
    for all 9 statuses and the top 5 dishes by quantity (name ascending on ties), all computed only
    from the owner's own restaurant.
    """
    now = datetime.now(timezone.utc)
    model = _build(None, mine, now)  # type: ignore[arg-type]
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
        other_restaurant = make_restaurant(db)
        _populate(db, restaurant, mine, now, model)
        _populate(db, other_restaurant, other, now, None)
        db.commit()

        res = client.get("/owner/stats", headers=auth_headers(owner))
        # Examples that straddle UTC midnight have an ambiguous "today": discard them.
        assume(datetime.now(timezone.utc).date() == now.date())
        assert res.status_code == 200, res.text
        body = res.json()

    assert body["total_orders"] == len(mine)
    assert body["orders_today"] == model["orders_today"]
    assert body["net_revenue"] == f"{model['net']:.2f}"
    assert body["status_counts"] == model["status_counts"]
    assert len(body["status_counts"]) == 9

    ratings = model["ratings"]
    if ratings:
        expected = (Decimal(sum(ratings)) / len(ratings)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert body["average_rating"] == float(expected)
    else:
        assert body["average_rating"] is None

    ranked = sorted(model["qty"].items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    assert body["top_dishes"] == [{"name": n, "quantity": q} for n, q in ranked]
