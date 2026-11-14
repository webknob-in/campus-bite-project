"""Property test for Reminder resolution on status change (Requirement 31.4)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import AdminReminderLog, OrderStatus
from app.services.order_state import Actor, transition
from tests.factories import (
    make_customer,
    make_order,
    make_owner,
    make_partner,
    make_reminder,
    make_restaurant,
)

S = OrderStatus
REMINDER_STATUSES = [S.PLACED, S.ACCEPTED, S.PREPARING, S.READY, S.ASSIGNED, S.OUT_FOR_DELIVERY]

# (scenario, expected to succeed)
SCENARIOS = [
    "owner_accept",
    "owner_assign",
    "customer_cancel",
    "partner_out",
    "partner_deliver",
    "service_transition",
    "rejected_409",
    "rejected_404",
    "rejected_403",
]

reminder_specs = st.dictionaries(st.sampled_from(REMINDER_STATUSES), st.booleans(), max_size=3)


def _states(db: Session, order_id: int) -> dict:
    db.expire_all()
    rows = db.scalars(select(AdminReminderLog).where(AdminReminderLog.order_id == order_id)).all()
    return {r.status_at_reminder: r.is_resolved for r in rows}


@given(
    scenario=st.sampled_from(SCENARIOS),
    own=reminder_specs,
    others=st.lists(reminder_specs, min_size=0, max_size=2),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_status_changes_resolve_reminders(
    client: TestClient, db_example, auth_headers, scenario: str, own: dict, others: list
) -> None:
    """Feature: campusbite-platform, Property 31: Status changes resolve Reminders

    **Validates: Requirements 31.4**
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
        partner = make_partner(db)
        start = {
            "owner_accept": S.PLACED,
            "owner_assign": S.READY,
            "customer_cancel": S.PLACED,
            "partner_out": S.ASSIGNED,
            "partner_deliver": S.OUT_FOR_DELIVERY,
            "service_transition": S.PLACED,
            "rejected_409": S.PLACED,
            "rejected_404": S.PLACED,
            "rejected_403": S.PLACED,
        }[scenario]
        order = make_order(
            db,
            start,
            customer=customer,
            restaurant=restaurant,
            partner=partner if start in (S.ASSIGNED, S.OUT_FOR_DELIVERY) else None,
        )
        for st_, resolved in own.items():
            make_reminder(db, order, status_at_reminder=st_, is_resolved=resolved)
        other_orders = []
        for spec in others:
            o = make_order(db, S.PLACED)
            for st_, resolved in spec.items():
                make_reminder(db, o, status_at_reminder=st_, is_resolved=resolved)
            other_orders.append(o)
        db.commit()

        before_own = _states(db, order.id)
        before_other = {o.id: _states(db, o.id) for o in other_orders}
        oid = order.id
        owner_h = auth_headers(owner)

        should_succeed = True
        if scenario == "owner_accept":
            res = client.patch(f"/owner/orders/{oid}/status", json={"status": "ACCEPTED"}, headers=owner_h)
            assert res.status_code == 200, res.text
        elif scenario == "owner_assign":
            res = client.post(
                f"/owner/orders/{oid}/assign", json={"delivery_partner_id": partner.id}, headers=owner_h
            )
            assert res.status_code == 200, res.text
        elif scenario == "customer_cancel":
            res = client.post(f"/orders/{oid}/cancel", headers=auth_headers(customer))
            assert res.status_code == 200, res.text
        elif scenario == "partner_out":
            res = client.patch(
                f"/partner/orders/{oid}/status", json={"status": "OUT_FOR_DELIVERY"}, headers=auth_headers(partner)
            )
            assert res.status_code == 200, res.text
        elif scenario == "partner_deliver":
            res = client.patch(
                f"/partner/orders/{oid}/status", json={"status": "DELIVERED"}, headers=auth_headers(partner)
            )
            assert res.status_code == 200, res.text
        elif scenario == "service_transition":
            transition(db, db.get(type(order), oid), S.ACCEPTED, Actor.RESTAURANT_OWNER)
            db.flush()
        else:
            should_succeed = False
            if scenario == "rejected_409":
                res = client.patch(f"/owner/orders/{oid}/status", json={"status": "READY"}, headers=owner_h)
                assert res.status_code == 409, res.text
            elif scenario == "rejected_404":
                stranger = make_owner(db)
                make_restaurant(db, stranger)
                db.commit()
                res = client.patch(
                    f"/owner/orders/{oid}/status", json={"status": "ACCEPTED"}, headers=auth_headers(stranger)
                )
                assert res.status_code == 404, res.text
            else:
                res = client.patch(
                    f"/owner/orders/{oid}/status", json={"status": "ACCEPTED"}, headers=auth_headers(customer)
                )
                assert res.status_code == 403, res.text

        after_own = _states(db, oid)
        if should_succeed:
            assert set(after_own) == set(before_own)
            assert all(after_own.values())
        else:
            assert after_own == before_own
        for o in other_orders:
            assert _states(db, o.id) == before_other[o.id]

        listing = client.get("/owner/reminders", params={"resolved": "false", "page_size": 100}, headers=owner_h)
        if listing.status_code == 200:
            ids = {item["order_id"] for item in listing.json()["items"]}
            if should_succeed:
                assert oid not in ids
            elif any(not v for v in before_own.values()):
                assert oid in ids
        else:
            assert listing.status_code == 422, listing.text
