"""Property test: rejected status operations leave the Order unchanged.

Feature: campusbite-platform, Property 16: Rejected status operations leave the Order unchanged

**Validates: Requirements 13.2, 13.3, 17.5, 18.3, 18.4, 21.7, 22.3**

The expected outcome comes from a small independent model (plain strings), not from the
implementation's transition table. Each example runs through the real HTTP routes.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import Order, OrderItem, OrderStatus, PaymentLedger
from tests.factories import make_customer, make_order, make_owner, make_partner, make_restaurant

STATUSES = [s.name for s in OrderStatus]

# (current, target) -> actor, per Requirement 22 (plain strings).
OWNER_STATUS = {("PLACED", "ACCEPTED"), ("ACCEPTED", "PREPARING"), ("PREPARING", "READY")}
PARTNER_STATUS = {("ASSIGNED", "OUT_FOR_DELIVERY"), ("OUT_FOR_DELIVERY", "DELIVERED")}

ASSIGNEES = ["partner", "customer", "owner", "unknown", "zero", "negative"]


def _snapshot(db: Session, order: Order) -> tuple:
    row = db.execute(
        select(
            Order.status,
            Order.status_updated_at,
            Order.updated_at,
            Order.delivered_at,
            Order.delivery_partner_id,
            Order.payment_status,
            Order.return_status,
            Order.total_amount,
        )
        .where(Order.id == order.id)
        .execution_options(populate_existing=True)
    ).one()
    items = db.execute(
        select(OrderItem.id, OrderItem.name, OrderItem.unit_price, OrderItem.quantity, OrderItem.line_total)
        .where(OrderItem.order_id == order.id)
        .order_by(OrderItem.id)
    ).all()
    ledger = db.execute(
        select(PaymentLedger.id, PaymentLedger.entry_type, PaymentLedger.amount, PaymentLedger.status)
        .where(PaymentLedger.order_id == order.id)
        .order_by(PaymentLedger.id)
    ).all()
    return tuple(row), [tuple(i) for i in items], [tuple(entry) for entry in ledger]


@given(
    current=st.sampled_from(STATUSES),
    op=st.sampled_from(["cancel", "owner_status", "assign", "partner_status"]),
    target=st.sampled_from(STATUSES + ["BOGUS"]),
    assignee=st.sampled_from(ASSIGNEES),
)
@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_rejected_status_operations_leave_order_unchanged(
    client: TestClient, db_example, auth_headers, current: str, op: str, target: str, assignee: str
) -> None:
    """Feature: campusbite-platform, Property 16: Rejected status operations leave the Order unchanged"""
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
        order = make_order(db, OrderStatus[current], customer=customer, restaurant=restaurant)
        db.commit()
        order_id = order.id
        has_partner = order.delivery_partner_id is not None

        spare_partner = make_partner(db)
        other_owner = make_owner(db)
        db.commit()

        expected_new: str | None  # status after a successful call, None when rejected
        accepted_codes: set[int]
        if op == "cancel":
            res_call = lambda: client.post(f"/orders/{order_id}/cancel", headers=auth_headers(customer))  # noqa: E731
            expected_new = "CANCELLED" if current == "PLACED" else None
            accepted_codes = {409}
        elif op == "owner_status":
            res_call = lambda: client.patch(  # noqa: E731
                f"/owner/orders/{order_id}/status", json={"status": target}, headers=auth_headers(owner)
            )
            if target == "BOGUS":
                expected_new, accepted_codes = None, {422}
            else:
                expected_new = target if (current, target) in OWNER_STATUS else None
                accepted_codes = {409}
        elif op == "assign":
            if assignee == "partner":
                assignee_id = spare_partner.id
            elif assignee == "customer":
                assignee_id = customer.id
            elif assignee == "owner":
                assignee_id = other_owner.id
            elif assignee == "unknown":
                assignee_id = 2_000_000_000
            elif assignee == "zero":
                assignee_id = 0
            else:
                assignee_id = -5
            res_call = lambda: client.post(  # noqa: E731
                f"/owner/orders/{order_id}/assign",
                json={"delivery_partner_id": assignee_id},
                headers=auth_headers(owner),
            )
            if assignee == "partner" and current == "READY":
                expected_new = "ASSIGNED"
            else:
                expected_new = None
            # A non-partner assignee is rejected with 400 (checked first); a valid partner on a
            # non-READY order is a 409.
            accepted_codes = {400} if assignee != "partner" else {409}
        else:
            # The order's own partner when it has one; otherwise a partner it is not assigned to.
            actor = None
            if has_partner:
                actor = db.get(Order, order_id).delivery_partner_id
                from app.models import User

                actor_user = db.get(User, actor)
            else:
                actor_user = spare_partner
            res_call = lambda: client.patch(  # noqa: E731
                f"/partner/orders/{order_id}/status", json={"status": target}, headers=auth_headers(actor_user)
            )
            if target == "BOGUS":
                expected_new, accepted_codes = None, {422}
            elif not has_partner:
                expected_new, accepted_codes = None, {404}
            else:
                expected_new = target if (current, target) in PARTNER_STATUS else None
                accepted_codes = {409}

        before = _snapshot(db, order)
        res = res_call()

        if expected_new is None:
            assert res.status_code in accepted_codes, (op, current, target, assignee, res.status_code, res.text)
            assert _snapshot(db, order) == before
        else:
            assert res.status_code == 200, (op, current, target, assignee, res.status_code, res.text)
            assert res.json()["status"] == expected_new
            after = _snapshot(db, order)
            assert after[0][0].name == expected_new
            assert after[1] == before[1] and after[2] == before[2]
            if op == "assign":
                assert after[0][4] == spare_partner.id
