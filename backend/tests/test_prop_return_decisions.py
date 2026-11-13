"""Property test for return decisions (Requirements 20.2, 20.3, 20.4, 23.2, 47.3)."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.main import app as fastapi_app
from app.models import LedgerType, Order, OrderStatus, PaymentLedger, PaymentStatus, ReturnStatus
from tests.factories import make_customer, make_order, make_owner, make_restaurant

decisions = st.lists(
    st.tuples(st.sampled_from(["approve", "reject"]), st.sampled_from(["own", "other"])),
    min_size=1,
    max_size=4,
)


@given(
    status=st.sampled_from(list(OrderStatus)),
    return_status=st.sampled_from(list(ReturnStatus)),
    cents=st.integers(min_value=1, max_value=10_000_000),
    steps=decisions,
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_return_decisions_keep_payment_state_consistent(
    client: TestClient, db_example, auth_headers, status, return_status, cents, steps
) -> None:
    """Feature: campusbite-platform, Property 19: Return decisions keep payment state consistent

    **Validates: Requirements 20.2, 20.3, 20.4, 23.2, 47.3**
    """
    total = Decimal(cents) / 100
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
        other_owner = make_owner(db)
        make_restaurant(db, other_owner)
        customer = make_customer(db)
        order = make_order(
            db, status, total=total, customer=customer, restaurant=restaurant, return_status=return_status
        )
        db.commit()
        order_id = order.id

        # Independent model of the order state.
        m_status, m_return = status, return_status
        m_payment = PaymentStatus.refunded if status is OrderStatus.REFUNDED else PaymentStatus.mock_paid
        m_refunds = 1 if m_payment is PaymentStatus.refunded else 0
        approved_seen = False
        rejected_seen = False

        for action, who in steps:
            actor = owner if who == "own" else other_owner
            before = sorted(
                (e.id, e.entry_type, e.amount, e.transaction_ref)
                for e in db.scalars(select(PaymentLedger).where(PaymentLedger.order_id == order_id))
            )
            res = client.post(f"/owner/returns/{order_id}/{action}", headers=auth_headers(actor))

            if who == "other":
                expected = 404
            elif m_return is ReturnStatus.requested and (
                action == "reject" or m_status is OrderStatus.DELIVERED
            ):
                expected = 200
                if action == "approve":
                    m_status, m_return, m_payment = (
                        OrderStatus.REFUNDED,
                        ReturnStatus.approved,
                        PaymentStatus.refunded,
                    )
                    m_refunds += 1
                    approved_seen = True
                else:
                    m_return = ReturnStatus.rejected
                    rejected_seen = True
            else:
                expected = 409
            assert res.status_code == expected, (action, who, res.text)
            if approved_seen or rejected_seen:
                pass

            db.expire_all()
            row = db.get(Order, order_id)
            assert row.status is m_status
            assert row.return_status is m_return
            assert row.payment_status is m_payment
            assert row.total_amount == total

            ledger = list(db.scalars(select(PaymentLedger).where(PaymentLedger.order_id == order_id)))
            pays = [e for e in ledger if e.entry_type is LedgerType.PAYMENT]
            refunds = [e for e in ledger if e.entry_type is LedgerType.REFUND]
            assert len(pays) == 1
            assert len(refunds) == m_refunds <= 1
            assert all(e.amount == total for e in refunds)
            assert len({e.transaction_ref for e in ledger}) == len(ledger)
            net = sum(e.amount for e in pays) - sum(e.amount for e in refunds)
            assert net == (0 if m_payment is PaymentStatus.refunded else total)
            if expected != 200:
                after = sorted((e.id, e.entry_type, e.amount, e.transaction_ref) for e in ledger)
                assert after == before
            if expected == 200 and action == "reject":
                assert len(refunds) == m_refunds and m_status is row.status

            # The customer sees the same ledger.
            detail = client.get(f"/orders/{order_id}", headers=auth_headers(customer))
            assert detail.status_code == 200, detail.text
            body = detail.json()
            assert body["status"] == m_status.value
            assert body["payment_status"] == m_payment.value
            shown = sorted(
                (e["entry_type"], Decimal(str(e["amount"]))) for e in body["ledger_entries"]
            )
            assert shown == sorted((e.entry_type.value, e.amount) for e in ledger)
