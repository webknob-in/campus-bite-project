"""Property test: one return request per Order (Requirements 15.2, 15.3, 15.4)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import Order, OrderStatus, ReturnStatus
from tests.factories import make_customer, make_order

_ALNUM = st.characters(categories=("L", "N"), codec="utf-8")
_PAD = st.text(alphabet=" \t\n", max_size=3)


def _body(n: int) -> st.SearchStrategy[str]:
    return st.text(alphabet=_ALNUM, min_size=n, max_size=n)


reasons = st.one_of(
    st.builds(lambda p, b, s: p + b + s, _PAD, st.text(alphabet=_ALNUM, min_size=1, max_size=40), _PAD),
    st.sampled_from([4, 5, 1000, 1001]).flatmap(_body),
    st.builds(lambda p, b, s: p + b + s, _PAD, _body(4), _PAD),  # trims to 4 -> invalid
    st.builds(lambda p, b, s: p + b + s, _PAD, _body(5), _PAD),  # trims to 5 -> valid
    st.text(alphabet=" \t", max_size=8),
)


@given(
    status=st.sampled_from(list(OrderStatus)),
    return_status=st.sampled_from(list(ReturnStatus)),
    attempts=st.lists(st.tuples(reasons, st.booleans()), min_size=1, max_size=4),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_one_return_request_per_order(
    client: TestClient, db_example, auth_headers, status, return_status, attempts
) -> None:
    """Feature: campusbite-platform, Property 18: One return request per Order

    **Validates: Requirements 15.2, 15.3, 15.4**
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

        owner = make_customer(db)
        other = make_customer(db)
        kwargs = {}
        if status is not OrderStatus.REFUNDED:
            kwargs["return_status"] = return_status
        order = make_order(db, status, customer=owner, **kwargs)
        db.commit()
        oid = order.id

        def snapshot() -> tuple:
            db.expire_all()
            o = db.get(Order, oid)
            return o.status, o.return_status, o.return_reason, o.return_requested_at

        initial = snapshot()
        successes = 0
        for reason, as_owner in attempts:
            before = snapshot()
            caller = owner if as_owner else other
            res = client.post(f"/orders/{oid}/return", json={"reason": reason}, headers=auth_headers(caller))
            valid = 5 <= len(reason.strip()) <= 1000
            can_succeed = (
                valid
                and as_owner
                and successes == 0
                and initial[0] is OrderStatus.DELIVERED
                and initial[1] is ReturnStatus.none
            )
            if can_succeed:
                assert res.status_code in (200, 201), res.text
                successes += 1
                after = snapshot()
                assert after[0] is OrderStatus.DELIVERED
                assert after[1] is ReturnStatus.requested
                assert after[2] == reason.strip()
                assert after[3] is not None
            else:
                if not valid:
                    assert res.status_code == 422, res.text
                elif not as_owner:
                    assert res.status_code == 404, res.text
                else:
                    assert res.status_code == 409, res.text
                assert snapshot() == before
        assert successes <= 1
