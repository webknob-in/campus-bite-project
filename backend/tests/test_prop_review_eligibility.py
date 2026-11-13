"""Property test for review eligibility (Requirements 14.2, 14.3, 14.4).

Precedence encoded from the code: body validation (422) happens first, then ownership (404),
then status (409), then the duplicate check (409).
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import OrderStatus, Review
from tests.factories import make_customer, make_order, make_review

ELIGIBLE = {OrderStatus.DELIVERED, OrderStatus.REFUNDED}

valid_ratings = st.integers(min_value=1, max_value=5)
invalid_ratings = st.one_of(
    st.just(0),
    st.just(6),
    st.integers(max_value=-1),
    st.integers(min_value=7, max_value=10_000),
    st.sampled_from([2.5, 3.0, 0.5, 5.5, "3", "five", "", True, False, None]),
)
ratings = st.one_of(valid_ratings, invalid_ratings)

_chars = st.characters(categories=("L", "N"), codec="utf-8")
valid_comments = st.one_of(
    st.none(),
    st.text(alphabet=_chars, min_size=1, max_size=1000),
    st.just("a" * 1000),
)
invalid_comments = st.integers(min_value=1001, max_value=1100).map(lambda n: "b" * n)
comments = st.one_of(valid_comments, invalid_comments)


def _rating_ok(r: object) -> bool:
    return isinstance(r, int) and not isinstance(r, bool) and 1 <= r <= 5


@given(
    status=st.sampled_from(list(OrderStatus)),
    has_review=st.booleans(),
    rating=ratings,
    comment=comments,
    other_customer=st.booleans(),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_review_eligibility(
    client: TestClient, db_example, auth_headers, status, has_review, rating, comment, other_customer
) -> None:
    """Feature: campusbite-platform, Property 17: Review eligibility

    **Validates: Requirements 14.2, 14.3, 14.4**
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

        order = make_order(db, status)
        if has_review:
            make_review(db, order, rating=3, comment="existing")
        caller = make_customer(db) if other_customer else order.customer
        db.commit()
        order_id, restaurant_id, customer_id = order.id, order.restaurant_id, caller.id
        headers = auth_headers(caller)

        def count() -> int:
            return db.scalar(select(func.count()).select_from(Review).where(Review.order_id == order_id))

        before = count()
        assert before == (1 if has_review else 0)

        payload_valid = _rating_ok(rating) and (comment is None or len(comment) <= 1000)
        if not payload_valid:
            expected = 422
        elif other_customer:
            expected = 404
        elif status not in ELIGIBLE or has_review:
            expected = 409
        else:
            expected = 201

        res = client.post(f"/orders/{order_id}/review", json={"rating": rating, "comment": comment}, headers=headers)
        assert res.status_code == expected, (res.status_code, res.text)

        after = count()
        if expected == 201:
            assert after == 1
            row = db.scalar(select(Review).where(Review.order_id == order_id))
            assert row.rating == rating
            assert row.comment == comment
            assert row.customer_id == customer_id
            assert row.restaurant_id == restaurant_id
            listing = client.get(f"/restaurants/{restaurant_id}/reviews")
            assert listing.status_code == 200
            assert any(i["id"] == row.id and i["rating"] == rating for i in listing.json()["items"])
        else:
            assert after == before
