"""Property test for the order list filters (Requirements 12.1, 24.2, 24.3).

``check_order_filters`` is endpoint-agnostic so the owner endpoint (``GET /owner/orders``) can reuse it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime, time, timedelta, timezone

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import Order, OrderStatus

from .factories import make_customer, make_order, make_owner, make_restaurant

BASE_DAY = date(2025, 3, 10)
STATUSES = list(OrderStatus)

# Offsets within a day: boundaries plus arbitrary times.
_boundary_times = st.sampled_from([time(0, 0, 0), time(23, 59, 59, 999999), time(12, 0, 0)])
_any_times = st.builds(
    time,
    st.integers(0, 23),
    st.integers(0, 59),
    st.integers(0, 59),
    st.sampled_from([0, 1, 999999]),
)
created_ats = st.builds(
    lambda d, t: datetime.combine(BASE_DAY + timedelta(days=d), t, tzinfo=timezone.utc),
    st.integers(0, 4),
    st.one_of(_boundary_times, _any_times),
)
order_specs = st.lists(st.tuples(st.sampled_from(STATUSES), created_ats), max_size=12)
days = st.one_of(st.none(), st.integers(-1, 5).map(lambda d: BASE_DAY + timedelta(days=d)))


def model_filter(
    orders: list[Order], status: OrderStatus | None, date_from: date | None, date_to: date | None
) -> list[Order]:
    """Reference model: status match AND created UTC date within [date_from, date_to], newest first."""
    kept = [
        o
        for o in orders
        if (status is None or o.status == status)
        and (date_from is None or o.created_at.astimezone(timezone.utc).date() >= date_from)
        and (date_to is None or o.created_at.astimezone(timezone.utc).date() <= date_to)
    ]
    return sorted(kept, key=lambda o: (o.created_at, o.id), reverse=True)


def check_order_filters(
    client: TestClient,
    path: str,
    headers: dict[str, str],
    expected_orders: list[Order],
    status: OrderStatus | None,
    date_from: date | None,
    date_to: date | None,
) -> None:
    """Call ``path`` with the filters and compare with the model built from ``expected_orders``."""
    params: dict[str, str] = {"page_size": "100"}
    if status is not None:
        params["status"] = status.value
    if date_from is not None:
        params["date_from"] = date_from.isoformat()
    if date_to is not None:
        params["date_to"] = date_to.isoformat()

    res = client.get(path, headers=headers, params=params)
    if date_from is not None and date_to is not None and date_from > date_to:
        assert res.status_code == 422, res.text
        return
    assert res.status_code == 200, res.text
    body = res.json()
    expected = model_filter(expected_orders, status, date_from, date_to)
    assert body["page"] == 1 and body["page_size"] == 100
    assert body["total"] == len(expected)
    assert [o["id"] for o in body["items"]] == [o.id for o in expected]

    # Paging with page_size=2 walks the same sequence and echoes its paging fields.
    seen: list[int] = []
    page = 1
    while True:
        p = client.get(path, headers=headers, params={**params, "page": str(page), "page_size": "2"})
        assert p.status_code == 200, p.text
        pb = p.json()
        assert pb["page"] == page and pb["page_size"] == 2 and pb["total"] == len(expected)
        assert len(pb["items"]) <= 2
        seen += [o["id"] for o in pb["items"]]
        if not pb["items"]:
            break
        page += 1
    assert seen == [o.id for o in expected]


@given(
    mine=order_specs,
    others=st.lists(st.tuples(st.sampled_from(STATUSES), created_ats), max_size=4),
    status=st.one_of(st.none(), st.sampled_from(STATUSES)),
    date_from=days,
    date_to=days,
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_customer_order_filters_match_model(
    client: TestClient,
    db_example: Callable[[], object],
    auth_headers: Callable[..., dict[str, str]],
    mine: list[tuple[OrderStatus, datetime]],
    others: list[tuple[OrderStatus, datetime]],
    status: OrderStatus | None,
    date_from: date | None,
    date_to: date | None,
) -> None:
    """Feature: campusbite-platform, Property 14: Order filters match model

    **Validates: Requirements 12.1, 24.2, 24.3**
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
        orders = [make_order(db, s, customer=customer, created_at=c) for s, c in mine]
        for s, c in others:
            make_order(db, s, customer=other, created_at=c)

        check_order_filters(
            client, "/orders/me", auth_headers(customer), orders, status, date_from, date_to
        )


def test_customer_order_filters_reject_invalid_params(client: TestClient, db, auth_headers) -> None:
    customer = make_customer(db)
    db.commit()  # a 422 makes get_db roll back; keep the customer
    headers = auth_headers(customer)
    assert client.get("/orders/me", headers=headers, params={"status": "bogus"}).status_code == 422
    assert client.get("/orders/me", headers=headers, params={"date_from": "nope"}).status_code == 422
    res = client.get(
        "/orders/me", headers=headers, params={"date_from": "2025-03-11", "date_to": "2025-03-10"}
    )
    assert res.status_code == 422


@given(
    mine=st.lists(st.tuples(st.sampled_from(STATUSES), created_ats, st.integers(0, 2)), max_size=12),
    others=st.lists(st.tuples(st.sampled_from(STATUSES), created_ats), max_size=4),
    status=st.one_of(st.none(), st.sampled_from(STATUSES)),
    date_from=days,
    date_to=days,
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_owner_order_filters_match_model(
    client: TestClient,
    db_example: Callable[[], object],
    auth_headers: Callable[..., dict[str, str]],
    mine: list[tuple[OrderStatus, datetime, int]],
    others: list[tuple[OrderStatus, datetime]],
    status: OrderStatus | None,
    date_from: date | None,
    date_to: date | None,
) -> None:
    """Feature: campusbite-platform, Property 14: Order filters match model

    **Validates: Requirements 17.2, 17.3**
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
        other_restaurant = make_restaurant(db)
        customers = [make_customer(db) for _ in range(3)]
        orders = [
            make_order(db, s, customer=customers[ci], restaurant=restaurant, created_at=c)
            for s, c, ci in mine
        ]
        for s, c in others:
            make_order(db, s, customer=customers[0], restaurant=other_restaurant, created_at=c)

        headers = auth_headers(owner)
        check_order_filters(client, "/owner/orders", headers, orders, status, date_from, date_to)

        if date_from is not None and date_to is not None and date_from > date_to:
            return
        params: dict[str, str] = {"page_size": "100"}
        if status is not None:
            params["status"] = status.value
        if date_from is not None:
            params["date_from"] = date_from.isoformat()
        if date_to is not None:
            params["date_to"] = date_to.isoformat()
        items = client.get("/owner/orders", headers=headers, params=params).json()["items"]
        by_id = {o.id: o for o in orders}
        for row in items:
            o = by_id[row["id"]]
            assert row["customer_name"] == o.customer.name
            if o.delivery_partner_id is None:
                assert row["delivery_partner"] is None
            else:
                assert row["delivery_partner"]["id"] == o.delivery_partner_id
